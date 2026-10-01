#!/usr/bin/env bash

render_restore_failure() {
  local err_file="$1" stage
  if grep -Fq 'backup package failed fresh verification' "$err_file" 2>/dev/null; then
    ui_bad '备份文件完整性复检失败，P07 已停止恢复。'
    ui_note '这个备份不能安全用于恢复；原网站没有修改，新网站也不会继续创建。'
    if grep -Fq 'symlink:' "$err_file" 2>/dev/null; then
      ui_note '原因：备份中发现旧版外部链接。升级 P07 后请重新创建一次备份。'
    else
      ui_note '建议：升级 P07 后重新备份一次，再执行恢复。'
    fi
    return 0
  fi

  stage="$(sed -n 's/.*Restore-As failed; stage=\([A-Z0-9_]*\);.*/\1/p' "$err_file" 2>/dev/null | tail -n1)"
  case "$stage" in
    TARGET_PREFLIGHT) ui_bad '恢复前目标检查没有通过，P07 已停止恢复。'; ui_note '原因：目标域名或目标目录当前不满足安全恢复条件。'; return 0 ;;
    CLOUDPANEL_SITE_CREATE) ui_bad 'CloudPanel 新网站创建没有完成，P07 已停止恢复。'; ui_note '原网站没有修改；本次新目标不会继续写入。'; return 0 ;;
    SITE_FILES_STAGE) ui_bad '网站文件解压没有完成，P07 已停止恢复。'; ui_note '原因：备份文件无法安全写入新网站临时目录。'; return 0 ;;
    SQLITE_SNAPSHOT_RESTORE) ui_bad 'SQLite 数据库快照恢复没有完成，P07 已停止恢复。'; ui_note '原因：独立 SQLite 一致性快照无法安全恢复到新网站。'; return 0 ;;
    SITE_FILES_VERIFY) ui_bad '恢复后的网站文件或 SQLite 数据校验没有通过。'; ui_note 'P07 已停止恢复并回滚本次新目标；原网站没有修改。'; return 0 ;;
    MYSQL_CREATE_IMPORT_VERIFY) ui_bad 'MySQL 数据库创建、导入或校验没有通过。'; ui_note 'P07 已停止恢复并清理本次新建数据库；原网站没有修改。'; return 0 ;;
    APPLICATION_CONFIG_REMAP) ui_bad '网站数据库配置无法安全改写到新数据库。'; ui_note 'P07 不会猜测配置位置，因此已停止恢复并回滚新目标。'; return 0 ;;
    SITE_OWNERSHIP_RECONCILIATION) ui_bad '新网站文件权限整理没有完成，P07 已停止恢复。'; return 0 ;;
    SITE_ATOMIC_COMMIT) ui_bad '新网站文件最终提交没有完成，P07 已停止恢复。'; return 0 ;;
    WORDPRESS_DOMAIN_REMAP) ui_bad 'WordPress 新域名替换或验证没有通过，P07 已停止恢复。'; return 0 ;;
    POST_RESTORE_PERMISSIONS) ui_bad 'CloudPanel 新网站权限最终整理没有完成，P07 已停止恢复。'; return 0 ;;
  esac

  if grep -Fq 'site nginx preflight failed' "$err_file" 2>/dev/null; then
    if grep -Fq 'reason=CONFIG_INVALID' "$err_file" 2>/dev/null; then
      ui_bad '网站 Nginx 配置自检没有通过，P07 已在创建新网站前停止。'
      ui_note '网站 Nginx 即使处于停止状态，也必须先保证配置可安全读取。'
      ui_note '本次没有创建新网站、没有修改 DNS，也没有修改原网站。'
    else
      ui_bad '网站 Nginx 配置检查没有通过，P07 已在创建新网站前停止。'
      ui_note '本次没有创建新网站、没有修改 DNS，也没有修改原网站。'
    fi
    return 0
  fi

  if grep -Fq 'Restore-As local verification failed' "$err_file" 2>/dev/null; then
    if grep -Fq 'nginx reload preflight failed' "$err_file" 2>/dev/null; then
      ui_bad '新网站已恢复，但 Nginx 配置自检没有通过，P07 已回滚新目标。'
      ui_note 'P07 没有继续重新加载 Nginx，也没有保留未验证的新站。'
      ui_note 'DNS 没有修改，原网站没有修改。'
      return 0
    elif grep -Fq 'nginx reload failed' "$err_file" 2>/dev/null; then
      if grep -Fq 'mode=SITE_NGINX' "$err_file" 2>/dev/null; then
        ui_bad '网站 Nginx 在恢复过程中变为不可用，P07 已回滚新目标。'
        ui_note 'CloudPanel 后台 Nginx 不会被当作网站 Nginx 使用。'
      elif grep -Fq 'mode=LIVE_MASTER_HUP' "$err_file" 2>/dev/null; then
        ui_bad 'CloudPanel 的实际 Nginx 没有在安全窗口内完成优雅重载，P07 已回滚新目标。'
        if grep -Fq 'reason=MASTER_NOT_FOUND' "$err_file" 2>/dev/null; then
          ui_note '原因：创建新站后，P07 在等待窗口内没有确认到稳定的 Nginx 主进程。'
        elif grep -Fq 'reason=MASTER_NOT_STABLE' "$err_file" 2>/dev/null; then
          ui_note '原因：Nginx 主进程仍在切换，P07 为避免误操作没有继续。'
        elif grep -Fq 'reason=MASTER_CHANGED' "$err_file" 2>/dev/null; then
          ui_note '原因：重载前后 Nginx 主进程发生变化，P07 为避免误操作已停止。'
        elif grep -Fq 'reason=MASTER_NOT_RUNNING' "$err_file" 2>/dev/null; then
          ui_note '原因：发送优雅重载后没有再确认到原 Nginx 主进程。'
        elif grep -Fq 'reason=SIGNAL_FAILED' "$err_file" 2>/dev/null; then
          ui_note '原因：系统没有接受对 Nginx 主进程的优雅重载信号。'
        else
          ui_note 'P07 没有重启 Nginx，也没有保留未验证的新站。'
        fi
      elif grep -Fq 'mode=SYSTEMD_MAIN_HUP' "$err_file" 2>/dev/null; then
        ui_bad '新网站已恢复，但 Nginx 常规重载和备用优雅重载都没有完成，P07 已回滚新目标。'
        if grep -Fq 'reason=SERVICE_NOT_ACTIVE' "$err_file" 2>/dev/null; then
          ui_note '原因：Nginx 服务状态异常，P07 没有继续保留未验证的新站。'
        elif grep -Fq 'reason=PERMISSION_DENIED' "$err_file" 2>/dev/null; then
          ui_note '原因：系统拒绝了 Nginx 重载操作。'
        else
          ui_note 'P07 已尝试由系统服务管理器对 Nginx 主进程执行优雅重载，但没有成功。'
        fi
      elif grep -Fq 'reason=PERMISSION_DENIED' "$err_file" 2>/dev/null; then
        ui_bad '新网站已恢复，但系统拒绝了 Nginx 重载操作，P07 已回滚新目标。'
      else
        ui_bad '新网站已恢复，但 Nginx 重新加载没有完成，P07 已回滚新目标。'
        ui_note '这表示新站配置已经生成，但运行中的 Nginx 没有成功加载它。'
      fi
      ui_note 'DNS 没有修改，原网站没有修改。'
      return 0
    fi
    if grep -Fq 'offline Nginx config verification failed' "$err_file" 2>/dev/null; then
      if grep -Fq 'target_vhost=MISSING' "$err_file" 2>/dev/null; then
        ui_bad '新网站数据已经恢复，但离线 Nginx 配置中没有找到这个新域名，P07 已回滚新目标。'
      elif grep -Fq 'target_listener=MISSING' "$err_file" 2>/dev/null; then
        ui_bad '新网站数据已经恢复，但离线 Nginx 配置中没有找到可用的网站监听配置，P07 已回滚新目标。'
      else
        ui_bad '新网站数据已经恢复，但离线 Nginx 配置校验没有通过，P07 已回滚新目标。'
      fi
      ui_note 'P07 没有启动或重启网站 Nginx；DNS 没有修改，原网站没有修改。'
      return 0
    fi
    if grep -Fq 'local Host routing verification failed' "$err_file" 2>/dev/null; then
      if grep -Fq 'target_listener=MISSING' "$err_file" 2>/dev/null; then
        ui_bad '新网站已恢复，Nginx 也有新站点配置，但没有发现可用于本机 HTTP 验证的 80 端口监听，P07 已回滚新目标。'
        ui_note 'P07 不会猜测服务器监听地址，也不会因此保留未验证的新站。'
      elif grep -Fq 'target_listener=UNREACHABLE' "$err_file" 2>/dev/null; then
        if grep -Fq 'target_transport=EMPTY_REPLY' "$err_file" 2>/dev/null; then
          ui_bad '新网站已恢复，也找到了 Nginx HTTP 监听，但 Nginx 返回了空响应，P07 已回滚新目标。'
          ui_note '这通常表示运行中的 Nginx 还没有真正加载这个新域名，或请求被默认站直接丢弃。'
        elif grep -Fq 'target_transport=CONNECT_FAILED' "$err_file" 2>/dev/null; then
          ui_bad '新网站已恢复，也找到了 Nginx HTTP 监听，但本机连接被拒绝，P07 已回滚新目标。'
        elif grep -Fq 'target_transport=TIMEOUT' "$err_file" 2>/dev/null; then
          ui_bad '新网站已恢复，也找到了 Nginx HTTP 监听，但本机连接超时，P07 已回滚新目标。'
        else
          ui_bad '新网站已恢复，P07 也找到了 Nginx 实际 HTTP 监听地址，但本机仍无法连通，已回滚新目标。'
        fi
        ui_note '这表示问题已经缩小到服务器本机监听/网络层，不是备份、SQLite 或数据库恢复本身。'
      elif grep -Fq 'target_vhost=MISSING' "$err_file" 2>/dev/null; then
        ui_bad '新网站已恢复，但 Nginx 还没有加载到这个新域名，P07 已回滚新目标。'
      elif grep -Fq 'target_vhost=PRESENT' "$err_file" 2>/dev/null; then
        ui_bad '新网站已恢复，Nginx 也已有新站点配置，但本机 HTTP 验证没有通过，P07 已回滚新目标。'
      else
        ui_bad '新网站已恢复，但本机 HTTP 路由验证没有通过，P07 已回滚新目标。'
      fi
    elif grep -Fq 'local SNI/vhost verification failed' "$err_file" 2>/dev/null; then
      ui_bad '新网站已恢复，但本机 HTTPS/SNI 路由验证没有通过，P07 已回滚新目标。'
    else
      ui_bad '新网站恢复后的本机自动验证没有通过，P07 已回滚新目标。'
    fi
    ui_note 'DNS 没有修改，原网站没有修改。'
    return 0
  fi

  if grep -Fq 'CloudPanel' "$err_file" 2>/dev/null; then
    ui_bad '网站面板操作没有完成，P07 已停止恢复。'
    ui_note '原网站没有修改；请先检查面板状态，再重新尝试。'
    return 0
  fi
  ui_bad '恢复没有完成，P07 已停止后续写入。'
  ui_note '原网站没有修改。技术错误已隐藏，避免把工程信息直接显示给普通用户。'
}
