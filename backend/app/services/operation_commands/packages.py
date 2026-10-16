import re
from urllib.parse import urlsplit

from .common import OperationSpec, OperationStep, action, boolean, field, fields, quote, read_spec, restore_new, rhel, selinux_context_check, shell, text, tools

TITLE = "软件仓库与升级"
REPO_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}"
REPO_DIR = "/etc/yum.repos.d"
ACTIONS = [
    action("list_repos", "查看软件仓库", "列出 DNF 仓库", False, []),
    action("upgrade_all", "升级所有软件包", "DNF 全量升级", True, []),
    action("add_repo", "新增仓库", "新增独立的受管 repo 文件", True, [
        field("repo", "仓库 ID"), field("url", "baseurl"),
        field("gpg_key", "GPG 公钥 URL"), field("enabled", "启用", "boolean", False, default=True),
    ]),
    action("update_repo", "更新仓库 URL", "只修改目标仓库段的 baseurl", True, [field("repo", "仓库 ID"), field("url", "新 baseurl")]),
    action("delete_repo", "删除仓库", "只删除目标仓库段", True, [field("repo", "仓库 ID")]),
]


def url(params: dict, key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not 0 < len(value) <= 2048 or re.search(r"[\s\\'\"<>#?]", value):
        raise ValueError(f"{key}必须是合法的 HTTP(S) URL")
    try:
        parts = urlsplit(value)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.username is not None or parts.password is not None or parts.query
                or parts.fragment or not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?", parts.netloc, re.ASCII)
                or not re.fullmatch(r"[A-Za-z0-9.-]+", parts.hostname, re.ASCII)
                or parts.hostname.startswith("-") or parts.hostname.endswith("-")
                or any(not label or label.startswith("-") or label.endswith("-") for label in parts.hostname.split("."))
                or (parts.port is not None and not 1 <= parts.port <= 65535)
                or not re.fullmatch(r"/[A-Za-z0-9_./~+:$,!-]*", parts.path or "/", re.ASCII)
                or re.search(r"(?i)(token|password|passwd|secret|api[-_]?key|credential)", parts.path)):
            raise ValueError
    except ValueError:
        raise ValueError(f"{key}必须是合法的 HTTP(S) URL") from None
    return value


def repo_scan(repo: str) -> str:
    # A duplicated section is ambiguous: refuse to select a file or mutate either copy.
    return f"""test -d {REPO_DIR} && test ! -L {REPO_DIR}
shopt -s nullglob
files=({REPO_DIR}/*.repo)
count=0
target=''
for file in "${{files[@]}}"; do
  test -f "$file" && test ! -L "$file" && test -r "$file"
  hits=$(awk -v id={quote(repo)} '
    /^[[:space:]]*\\[[^]]+\\][[:space:]]*$/ {{
      line=$0; sub(/^[[:space:]]*\\[/, "", line); sub(/\\][[:space:]]*$/, "", line)
      if (line == id) n++
    }} END {{print n+0}}' "$file")
  count=$((count + hits))
  if ((hits > 0)); then target="$file"; fi
done"""


def repo_snapshot(repo: str, exists: bool) -> str:
    return repo_scan(repo) + f"""
test "$count" -eq {1 if exists else 0} || {{ echo '仓库 ID 不唯一或不存在' >&2; exit 1; }}
for file in "${{files[@]}}"; do sha256sum -- "$file"; done"""


def inspect() -> str:
    return shell(tools("awk") + "\ndnf -q repolist --all | awk 'BEGIN {print \"repo id\\tstatus\"} "
                 "$1 == \"repo\" && $2 == \"id\" {next} "
                 "NF >= 2 && $1 ~ /^[A-Za-z0-9_.-]+$/ {"
                 "if ($NF ~ /^(enabled|disabled)$/) {print $1 \"\\t\" $NF; next} "
                 "if (NF >= 3 && $(NF-1) ~ /^(enabled|disabled):$/ && $NF ~ /^[0-9,]+$/) "
                 "{print $1 \"\\t\" $(NF-1) $NF; next}} "
                 "{exit 1}'")


def build(name: str, params: dict) -> OperationSpec:
    if name not in ACTION_TITLE:
        raise ValueError("不支持的运维操作")
    if name == "list_repos":
        fields(params, set())
        return read_spec("查看软件仓库", inspect())
    if name == "upgrade_all":
        fields(params, set())
        pre = rhel() + "\n" + tools("rpm", "sha256sum", "sort") + "\nrpm -qa | sort | sha256sum"
        pre += f"\nfor file in {REPO_DIR}/*.repo; do test -f \"$file\" || continue; test ! -L \"$file\"; sha256sum -- \"$file\"; done"
        # DNF returns 100 when further updates remain. A nonzero result is verification failure.
        return OperationSpec(ACTION_TITLE[name], True, shell(pre),
                             (OperationStep(ACTION_TITLE[name], shell("dnf -y upgrade"), 3600),),
                             shell("dnf -q check-update"))
    fields(params, {"repo", "url", "gpg_key", "enabled"} if name == "add_repo" else
           {"repo", "url"} if name == "update_repo" else {"repo"},
           {"repo", "url", "gpg_key"} if name == "add_repo" else
           {"repo", "url"} if name == "update_repo" else {"repo"})
    repo = text(params, "repo", REPO_RE, "仓库 ID", 64)
    if ".." in repo:
        raise ValueError("仓库 ID 不允许连续点")
    new_url = url(params, "url") if name != "delete_repo" else ""
    key = url(params, "gpg_key") if name == "add_repo" else ""
    enabled = boolean(params, "enabled", True) if name == "add_repo" else True
    snapshot = repo_snapshot(repo, name != "add_repo")
    pre = rhel() + "\n" + tools("awk", "sha256sum", "mktemp", "chmod", "mv", "cp", "ln") + "\n" + snapshot
    if name == "add_repo":
        pre += "\n" + selinux_context_check()
        path = f"{REPO_DIR}/autops-{repo}.repo"
        pre += f"\ntest ! -e {quote(path)} && test ! -L {quote(path)}"
        content = f"[{repo}]\nname={repo}\nbaseurl={new_url}\nenabled={int(enabled)}\ngpgcheck=1\ngpgkey={key}\n"
        command = snapshot + "\n" + selinux_context_check() + f"""
test ! -e {quote(path)} && test ! -L {quote(path)}
tmp=$(mktemp {REPO_DIR}/.autops-repo.XXXXXX)
trap 'rm -f -- "$tmp"' EXIT
printf '%s' {quote(content)} > "$tmp"
chmod 0644 "$tmp"
ln -- "$tmp" {quote(path)}
{restore_new(path)}"""
        verify = repo_scan(repo) + f"\ntest \"$count\" -eq 1 && test \"$target\" = {quote(path)}\ngrep -Fx -- {quote('baseurl=' + new_url)} \"$target\" >/dev/null"
    else:
        command = snapshot + f"""
tmp=$(mktemp {REPO_DIR}/.autops-repo.XXXXXX)
trap 'rm -f -- "$tmp"' EXIT
awk -v id={quote(repo)} -v url={quote(new_url)} -v remove={1 if name == 'delete_repo' else 0} '
  /^[[:space:]]*\\[[^]]+\\][[:space:]]*$/ {{
    line=$0; sub(/^[[:space:]]*\\[/, "", line); sub(/\\][[:space:]]*$/, "", line)
    active=(line == id)
    if (active && !remove) {{ print; print "baseurl=" url; next }}
  }}
  active && (remove || /^[[:space:]]*(baseurl|mirrorlist|metalink)[[:space:]]*=/) {{next}}
  {{print}}
' "$target" > "$tmp"
cp --attributes-only --preserve=all -- "$target" "$tmp"
mv -f -- "$tmp" "$target"
"""
        verify = repo_scan(repo) + ("\ntest \"$count\" -eq 0" if name == "delete_repo" else
                                    f"\ntest \"$count\" -eq 1\ngrep -Fx -- {quote('baseurl=' + new_url)} \"$target\" >/dev/null")
    return OperationSpec(ACTION_TITLE[name], True, shell(pre),
                         (OperationStep(ACTION_TITLE[name], shell(command)),), shell(verify))


ACTION_TITLE = {item["id"]: item["title"] for item in ACTIONS}
