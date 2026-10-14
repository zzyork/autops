from .common import OperationSpec, OperationStep, action, boolean, choice, field, fields, quote, read_spec, shell, text, tools

TITLE = "磁盘"
ACTIONS = [
    action("list", "查看磁盘", "只读列出磁盘、分区、签名与挂载", False, []),
    action("provision", "初始化裸盘并挂载", "GPT 分区、LVM、文件系统和挂载；不可撤销", True, [
        field("device", "整盘设备（如 /dev/sdb）"),
        field("vg", "新卷组名"), field("lv", "新逻辑卷名"),
        field("filesystem", "文件系统", "select", options=[{"label": "XFS", "value": "xfs"}, {"label": "ext4", "value": "ext4"}]),
        field("mount_point", "新挂载目录（/data 或 /mnt 下）"),
        field("automount", "开机挂载", "boolean", False, default=False),
    ]),
]


def inspect() -> str:
    return shell(tools("lsblk", "findmnt", "swapon", "pvs", "vgs", "lvs") + """
lsblk -o NAME,PATH,TYPE,SIZE,FSTYPE,UUID,MOUNTPOINTS,MODEL,SERIAL,WWN
findmnt --real -o SOURCE,TARGET,FSTYPE
swapon --show=NAME,TYPE,SIZE
pvs -o pv_name,vg_name
vgs -o vg_name,vg_size
lvs -o lv_name,vg_name,lv_size""")


def check(device: str, vg: str, lv: str, mount_point: str) -> str:
    disk = quote(device)
    mp = quote(mount_point)
    vgq = quote(vg)
    lvq = quote(lv)
    return tools("lsblk", "readlink", "wipefs", "blkid", "pvs", "vgs", "lvs", "mdadm", "swapon", "wc", "grep", "cat", "dirname", "ls",
                 "findmnt", "blockdev", "awk", "sha256sum", "parted", "partprobe", "udevadm",
                 "pvcreate", "vgcreate", "lvcreate", "mount", "mkdir") + f"""
test -b {disk} && test ! -L {disk}
disk=$(readlink -e -- {disk})
test "$disk" = {disk}
type=$(lsblk -dn -o TYPE -- "$disk"); test "$type" = disk
layout=$(lsblk -nrpo NAME,TYPE -- "$disk"); test "$(printf '%s\\n' "$layout" | wc -l)" -eq 1
read_only=$(lsblk -dn -o RO -- "$disk"); test "$read_only" = 0
size=$(lsblk -dn -o SIZE -b -- "$disk"); test "$size" -ge 1073741824
mounts=$(lsblk -nrpo MOUNTPOINTS -- "$disk"); test -z "$mounts"
fs=$(lsblk -dn -o FSTYPE -- "$disk"); test -z "$fs"
signatures=$(wipefs -n --noheadings -O TYPE -- "$disk"); test -z "$signatures"
rc=0; blkid -p -- "$disk" >/dev/null 2>&1 || rc=$?
test "$rc" -eq 2 || {{ echo '设备存在签名或 blkid 探测失败' >&2; exit 1; }}
rc=0; mdadm --examine -- "$disk" >/dev/null 2>&1 || rc=$?
test "$rc" -eq 1 || {{ echo 'RAID 检查发现占用或失败' >&2; exit 1; }}
test -d "/sys/class/block/${{disk##*/}}/holders"
test -d "/sys/class/block/${{disk##*/}}/slaves"
holders=$(ls -A "/sys/class/block/${{disk##*/}}/holders"); test -z "$holders"
slaves=$(ls -A "/sys/class/block/${{disk##*/}}/slaves"); test -z "$slaves"
pvlist=$(pvs --noheadings -o pv_name)
swaplist=$(swapon --noheadings --raw --show=NAME)
vglist=$(vgs --noheadings -o vg_name)
lvlist=$(lvs --noheadings -o lv_name)
rc=0; printf '%s\\n' "$pvlist" | awk -v disk="$disk" '$1 == disk {{found=1}} END {{exit !found}}' || rc=$?; test "$rc" -eq 1
rc=0; printf '%s\\n' "$swaplist" | awk -v disk="$disk" '$1 == disk {{found=1}} END {{exit !found}}' || rc=$?; test "$rc" -eq 1
rc=0; printf '%s\\n' "$vglist" | awk -v vg={vgq} '$1 == vg {{found=1}} END {{exit !found}}' || rc=$?; test "$rc" -eq 1
rc=0; printf '%s\\n' "$lvlist" | awk -v lv={lvq} '$1 == lv {{found=1}} END {{exit !found}}' || rc=$?; test "$rc" -eq 1
root=$(findmnt -rn -o SOURCE --target /)
[[ "$root" == /dev/* ]] && test -b "$root"
root=$(readlink -e -- "$root")
test -n "$root"
root_tree=$(lsblk -snpo NAME -- "$root")
if printf '%s\\n' "$root_tree" | grep -Fx -- "$disk" >/dev/null; then exit 1; fi
test -d /dev/disk/by-id
stable=''
for id in /dev/disk/by-id/*; do
  test -L "$id" || continue
  [[ "$id" != *-part[0-9]* ]] || continue
  target=$(readlink -e -- "$id")
  if test "$target" = "$disk"; then stable="$id"; break; fi
done
test -n "$stable" || {{ echo '没有可用的稳定设备标识' >&2; exit 1; }}
test -f /etc/fstab && test ! -L /etc/fstab && test -r /etc/fstab
for id in /dev/disk/by-id/*; do
  test -L "$id" || continue
  target=$(readlink -e -- "$id")
  if test "$target" = "$disk"; then
    rc=0; awk -v alias="$id" '$1 !~ /^#/ && $1 == alias {{found=1}} END {{exit !found}}' /etc/fstab || rc=$?
    test "$rc" -eq 1
  fi
done
test -d "$(dirname -- {mp})"
test ! -e {mp} && test ! -L {mp}
parent={mp}
while test "$parent" != /; do
  parent=$(dirname -- "$parent")
  test ! -L "$parent" && test -d "$parent"
done
mounted_targets=$(findmnt --kernel -rn -o TARGET)
rc=0; printf '%s\\n' "$mounted_targets" | grep -Fx -- {mp} >/dev/null || rc=$?
test "$rc" -eq 1 || {{ echo '挂载点已占用或探测失败' >&2; exit 1; }}
rc=0; awk -v mp={mp} -v disk="$disk" -v stable="$stable" -v vg={vgq} -v lv={lvq} '
  $1 !~ /^#/ && ($2 == mp || $1 == disk || $1 == stable || $1 == "/dev/" vg "/" lv) {{found=1}}
  END {{exit !found}}' /etc/fstab || rc=$?; test "$rc" -eq 1
printf 'device=%s by-id=%s size=%s sysfs=%s vg=%s lv=%s mount=%s\\n' \
  "$disk" "$stable" "$(blockdev --getsize64 "$disk")" \
  "$(cat "/sys/class/block/${{disk##*/}}/dev")" {vgq} {lvq} {mp}
sha256sum /etc/fstab"""


def build(name: str, params: dict) -> OperationSpec:
    if name == "list":
        fields(params, set())
        return read_spec("查看磁盘", inspect())
    fields(params, {"device", "vg", "lv", "filesystem", "mount_point", "automount"},
           {"device", "vg", "lv", "filesystem", "mount_point"})
    device = text(params, "device", r"/dev/(?:sd[a-z]+|vd[a-z]+|xvd[a-z]+|nvme[0-9]+n[0-9]+|mmcblk[0-9]+)", "整盘设备", 64)
    vg = text(params, "vg", r"[A-Za-z_][A-Za-z0-9_.-]*", "卷组名", 64)
    lv = text(params, "lv", r"[A-Za-z_][A-Za-z0-9_.-]*", "逻辑卷名", 64)
    if any(".." in value or value.endswith("-") or value in {".", ".."} for value in (vg, lv)):
        raise ValueError("LVM 名称无效")
    filesystem = choice(params, "filesystem", {"xfs", "ext4"}, "文件系统")
    mount_point = text(params, "mount_point", r"/(?:data|mnt)(?:/[A-Za-z0-9_.-]+)*", "挂载路径", 256)
    if mount_point in {"/mnt", "/data"} or any(part in {".", ".."} for part in mount_point.split("/")):
        raise ValueError("挂载点必须是 /data 或 /mnt 下的新目录")
    automount = boolean(params, "automount")
    pre = check(device, vg, lv, mount_point) + "\n" + tools("mkfs." + filesystem)
    if automount:
        pre += "\n" + tools("lsattr") + """
test -w /etc/fstab
fstab_attributes=$(lsattr -d -- /etc/fstab)
fstab_flags=${fstab_attributes%% *}
[[ "$fstab_flags" != *i* ]] || { echo 'fstab 不可修改' >&2; exit 1; }
fstab_options=$(findmnt -rn -o OPTIONS --target /etc/fstab)
case ",$fstab_options," in *,ro,*) echo 'fstab 文件系统只读' >&2; exit 1;; esac"""
    disk = quote(device)
    logical = quote(f"/dev/{vg}/{lv}")
    mp = quote(mount_point)
    # Revalidate immediately before repartitioning. Never use --force or wipe an existing signature.
    create = pre + f"""
parted -s -- {disk} mklabel gpt
parted -s -- {disk} mkpart primary 1MiB 100%
partprobe -- {disk}
udevadm settle
parts_output=$(lsblk -nrpo NAME,TYPE -- {disk})
mapfile -t parts < <(printf '%s\\n' "$parts_output" | awk '$2 == "part" {{print $1}}')
test "${{#parts[@]}}" -eq 1
part="${{parts[0]}}"
test "$(lsblk -dn -o PKNAME -- "$part")" = {quote(device.rsplit('/', 1)[-1])}
test -b "$part"
pvcreate -- "$part"
vgcreate -- {quote(vg)} "$part"
lvcreate -n {quote(lv)} -l 100%FREE -- {quote(vg)}
mkfs.{filesystem} -- {logical}
uuid=$(blkid -s UUID -o value -- {logical})
[[ "$uuid" =~ ^[A-Fa-f0-9-]{{8,64}}$ ]]
test ! -e {mp} && test ! -L {mp}
mkdir -- {mp}
mount -- {logical} {mp}
test "$(findmnt -rn -o TARGET --mountpoint {mp})" = {mp}"""
    if automount:
        create += f"""
rc=0; awk -v mp={mp} -v uuid="UUID=$uuid" '$1 !~ /^#/ && ($2 == mp || $1 == uuid) {{found=1}} END {{exit !found}}' /etc/fstab || rc=$?; test "$rc" -eq 1
printf '%s\\n' "UUID=$uuid {mount_point} {filesystem} defaults 0 0" >> /etc/fstab"""
    verify = f"""test -b {logical}
test "$(blkid -s TYPE -o value -- {logical})" = {quote(filesystem)}
test "$(findmnt -rn -o TARGET --mountpoint {mp})" = {mp}
source=$(findmnt -rn -o SOURCE --mountpoint {mp})
test "$(readlink -e -- "$source")" = "$(readlink -e -- {logical})"
uuid=$(blkid -s UUID -o value -- {logical})
test -n "$uuid"
"""
    if automount:
        verify += f"\ngrep -Fx -- \"UUID=$uuid {mount_point} {filesystem} defaults 0 0\" /etc/fstab >/dev/null"
    return OperationSpec("初始化裸盘并挂载", True, shell(pre),
                         (OperationStep("分区、建卷、格式化并挂载", shell(create), 600),), shell(verify))
