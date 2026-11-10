"""严格时间与已知非报错记录筛选；先筛选再有界保留原文，不推断缺失年份。"""

_KNOWN_NON_ERROR_FILTER = r"""
function known_non_error_log(line, message, pid, event, suffix, command, audit_time) {
    message = line
    if (!sub(/^\[?[0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}([.,][0-9]+)?(Z|[+-][0-9]{2}:?[0-9]{2})?\]?[[:space:]]+/, "", message)) {
        return 0
    }
    # 此条内核 err 仅建议端点使用不同奇偶性，配置仍写入；不排除其他内核或端口错误。
    if (match(message, /^[^[:space:]]+[[:space:]]+kernel:[[:space:]]+/)) {
        return substr(message, RLENGTH + 1) == "ip_local_port_range: prefer different parity for start/end values."
    }
    if (!match(message, /^[^[:space:]]+[[:space:]]+umount\[[0-9]+\]:[[:space:]]+/)) {
        return 0
    }
    pid = substr(message, 1, RLENGTH)
    message = substr(message, RLENGTH + 1)
    sub(/^[^[:space:]]+[[:space:]]+umount\[/, "", pid)
    sub(/\]:[[:space:]]+$/, "", pid)

    # 只识别已知审计模板，日志头与正文 PID 必须一致；不按进程名或 ret=0 泛化排除。
    if (message ~ /^util_linux umount start /) {
        event = "^util_linux umount start pid=" pid ", parent pid=[0-9]+ cmd="
        suffix = ",start_time="
    } else if (message ~ /^util_linux umount finish /) {
        event = "^util_linux umount finish pid=" pid ", parent pid=[0-9]+ ret=0, cmd="
        suffix = ", finish_time="
    } else {
        return 0
    }
    command = "\"[ ]?/usr/bin/umount [^\"[:cntrl:]]+\""
    audit_time = "(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    audit_time = audit_time " +[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}"
    return message ~ (event command suffix audit_time "$")
}
"""

JOURNAL_FILTER = _KNOWN_NON_ERROR_FILTER + r"""
!known_non_error_log($0) { print }
"""

_TIME_FILTER_BODY = _KNOWN_NON_ERROR_FILTER + r"""
function log_time(line, stamp, spec, rest, utc, offset, zone, hours, minutes, value, standard, daylight) {
    fractional = 0
    stamp = line
    sub(/^\[/, "", stamp)
    if (stamp !~ /^[0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}/) {
        return -1
    }
    spec = substr(stamp, 1, 19)
    gsub(/[-\/T:]/, " ", spec)
    rest = substr(stamp, 20)
    if (match(rest, /^[.,][0-9]+/)) {
        fractional = substr(rest, 2, RLENGTH - 1) ~ /[1-9]/
        rest = substr(rest, RLENGTH + 1)
    }
    utc = 0
    offset = 0
    if (substr(rest, 1, 1) == "Z") {
        utc = 1
        rest = substr(rest, 2)
    } else if (match(rest, /^[+-][0-9]{2}:?[0-9]{2}/)) {
        zone = substr(rest, 1, RLENGTH)
        rest = substr(rest, RLENGTH + 1)
        gsub(/:/, "", zone)
        hours = substr(zone, 2, 2) + 0
        minutes = substr(zone, 4, 2) + 0
        if (hours > 23 || minutes > 59) {
            return -1
        }
        offset = (hours * 3600 + minutes * 60) * (substr(zone, 1, 1) == "-" ? -1 : 1)
        utc = 1
    }
    if (rest !~ /^\]?[[:space:]]/) {
        return -1
    }
    value = log_mktime(spec, utc)
    # mktime 会归一化无效日期；回转核对才能拒绝 2 月 30 日等输入。
    if (value < 0 || strftime("%Y %m %d %H %M %S", value, utc) != spec) {
        return -1
    }
    # 无时区时间在夏令时回拨期间可能对应两个时刻，不能替日志选择其中一个。
    if (!utc) {
        standard = mktime(spec " 0")
        daylight = mktime(spec " 1")
        if (standard != daylight &&
            strftime("%Y %m %d %H %M %S", standard) == spec &&
            strftime("%Y %m %d %H %M %S", daylight) == spec) {
            return -1
        }
    }
    return value - offset
}

BEGIN {
    # 验证 UTC 换算及格式化能力；不支持时不能改用未经时间过滤的输出。
    if (log_mktime("2000 01 01 00 00 00", 1) != 946684800 ||
        strftime("%Y %m %d %H %M %S", 946684800, 1) != "2000 01 01 00 00 00") {
        invalid_tool = 1
        exit 127
    }
}

{
    if (tolower($0) !~ keywords) {
        next
    }
    recorded = log_time($0)
    if (recorded < 0) {
        unknown++
        next
    }
    # 时间无法判定的记录仍计入 unknown，不能因已知非报错模板而推断其属于本次窗口。
    if (known_non_error_log($0)) {
        next
    }
    # 窗口按整数秒定义，避免把边界外的小数秒浮点舍入到窗口内。
    if (recorded >= start && (recorded < finish || (recorded == finish && !fractional))) {
        count++
        entries[count % limit] = $0
    }
}

END {
    if (!invalid_tool) {
        printf "AUTOPS_LOG_WINDOW %.0f\n", unknown
        first = count > limit ? count - limit + 1 : 1
        for (position = first; position <= count; position++) {
            print entries[position % limit]
        }
    }
}
"""

TIME_FILTER = r"""
function log_mktime(spec, utc) {
    return mktime(spec " -1", utc)
}
""" + _TIME_FILTER_BODY

# gawk 4.0 不支持 mktime 的 UTC 参数；UTC 按公历换算，本地时间继续使用系统时区。
# 两条命令共用回转校验、夏令时歧义检查及有界输出逻辑。
LEGACY_TIME_FILTER = r"""
function log_mktime(spec, utc, parts, year, month, days, month_days) {
    if (!utc) {
        return mktime(spec " -1")
    }
    split(spec, parts, " ")
    year = parts[1] + 0
    month = parts[2] + 0
    if (year < 1970 || month < 1 || month > 12) {
        return -1
    }
    # 统计 Unix 纪元后完整年份及月份的天数，闰年遵循 4/100/400 年规则。
    days = 365 * (year - 1970) + int((year - 1) / 4) - int(1969 / 4) \
           - int((year - 1) / 100) + int(1969 / 100) \
           + int((year - 1) / 400) - int(1969 / 400)
    split("0 31 59 90 120 151 181 212 243 273 304 334", month_days, " ")
    days += month_days[month] + parts[3] - 1
    if (month > 2 && year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)) {
        days++
    }
    return days * 86400 + parts[4] * 3600 + parts[5] * 60 + parts[6]
}
""" + _TIME_FILTER_BODY
