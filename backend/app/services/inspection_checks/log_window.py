"""目标主机上的严格时间筛选；先筛选再有界保留原文，不推断缺失年份。"""

TIME_FILTER = r"""
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
    value = mktime(spec " -1", utc)
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
    # 验证 UTC 参数可用；不支持时不能改用未经时间过滤的输出。
    if (mktime("2000 01 01 00 00 00", 1) != 946684800 ||
        strftime("%Y", 946684800, 1) != "2000") {
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
