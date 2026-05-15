#!/bin/bash
# update_db.sh — 执行 migrations 目录下的 SQL 迁移脚本。
#
# 用法：
#   ./update_db.sh --help
#   ./update_db.sh                                    # 使用默认配置执行所有迁移
#   ./update_db.sh --config config/manager.yaml       # 从 YAML 配置读取数据库连接
#   ./update_db.sh --host 127.0.0.1 --port 3306 --user root --password 'xxx' --database deeppool
#   ./update_db.sh --file 011_guardrails.sql          # 仅执行指定的迁移文件
#   ./update_db.sh --from 008                         # 从指定编号开始执行
#   ./update_db.sh --dry-run                          # 仅打印将要执行的文件，不实际执行
set -euo pipefail

# ============================================================
# 默认值
# ============================================================
DB_HOST="127.0.0.1"
DB_PORT="3306"
DB_USER="root"
DB_PASSWORD=""
DB_DATABASE="deeppool"
CONFIG_FILE=""
MIGRATION_DIR=""
SPECIFIC_FILE=""
FROM_NUM=""
DRY_RUN=false

# ============================================================
# 帮助信息
# ============================================================
show_help() {
  cat <<EOF
用法: ./update_db.sh [选项]

数据库迁移脚本 — 按顺序执行 migrations 目录下的 SQL 文件。

数据库连接参数:
  --config <file>       从 YAML 配置文件读取数据库连接信息 (解析 mysql 段)
                        例如: --config config/manager.yaml
  --host <host>         数据库主机地址 (默认: 127.0.0.1)
  --port <port>         数据库端口 (默认: 3306)
  --user <user>         数据库用户名 (默认: root)
  --password <pass>     数据库密码
  --database <db>       数据库名 (默认: deeppool)

迁移控制参数:
  --dir <path>          migrations 目录路径 (默认: 脚本同级 migrations/)
  --file <filename>     仅执行指定的迁移文件 (例如: 011_guardrails.sql)
  --from <number>       从指定编号开始执行 (例如: 008 表示从 008 开始)
  --dry-run             仅打印将要执行的文件列表，不实际执行

其他:
  --help, -h            显示此帮助信息

示例:
  # 使用配置文件连接数据库，执行所有迁移
  ./update_db.sh --config config/manager.yaml

  # 手动指定连接参数
  ./update_db.sh --host 127.0.0.1 --user root --password 'root@123' --database deeppool

  # 仅执行 011 号迁移
  ./update_db.sh --config config/manager.yaml --file 011_guardrails.sql

  # 从 008 号开始执行
  ./update_db.sh --config config/manager.yaml --from 008

  # 预览将要执行的迁移
  ./update_db.sh --config config/manager.yaml --dry-run

注意:
  - SQL 文件按文件名前缀数字排序执行 (002, 003, 004, ...)
  - 每个 SQL 文件使用 CREATE TABLE IF NOT EXISTS 等幂等语句，可安全重复执行
  - 建议在执行前先使用 --dry-run 预览
EOF
  exit 0
}

# ============================================================
# 参数解析
# ============================================================
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)
      show_help
      ;;
    --config)
      CONFIG_FILE="$2"; shift 2
      ;;
    --host)
      DB_HOST="$2"; shift 2
      ;;
    --port)
      DB_PORT="$2"; shift 2
      ;;
    --user)
      DB_USER="$2"; shift 2
      ;;
    --password)
      DB_PASSWORD="$2"; shift 2
      ;;
    --database)
      DB_DATABASE="$2"; shift 2
      ;;
    --dir)
      MIGRATION_DIR="$2"; shift 2
      ;;
    --file)
      SPECIFIC_FILE="$2"; shift 2
      ;;
    --from)
      FROM_NUM="$2"; shift 2
      ;;
    --dry-run)
      DRY_RUN=true; shift
      ;;
    *)
      echo "[ERROR] 未知参数: $1"
      echo "使用 --help 查看帮助信息"
      exit 1
      ;;
  esac
done

# ============================================================
# 路径设置
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$MIGRATION_DIR" ]; then
  MIGRATION_DIR="$SCRIPT_DIR/migrations"
fi

if [ ! -d "$MIGRATION_DIR" ]; then
  echo "[ERROR] migrations 目录不存在: $MIGRATION_DIR"
  exit 1
fi

# ============================================================
# 从 YAML 配置文件解析数据库连接信息
# ============================================================
if [ -n "$CONFIG_FILE" ]; then
  # 支持相对路径
  if [[ "$CONFIG_FILE" != /* ]]; then
    CONFIG_FILE="$SCRIPT_DIR/$CONFIG_FILE"
  fi

  if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] 配置文件不存在: $CONFIG_FILE"
    exit 1
  fi

  echo "==> 从配置文件读取数据库连接: $CONFIG_FILE"

  # 使用 grep + sed 简单解析 YAML (避免依赖 yq/python)
  parse_yaml_value() {
    local key="$1"
    grep -A 20 "^mysql:" "$CONFIG_FILE" | grep "^  ${key}:" | head -1 | sed 's/.*: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | sed 's/ *#.*//' | xargs
  }

  YAML_HOST=$(parse_yaml_value "host")
  YAML_PORT=$(parse_yaml_value "port")
  YAML_USER=$(parse_yaml_value "user")
  YAML_PASSWORD=$(parse_yaml_value "password")
  YAML_DATABASE=$(parse_yaml_value "database")

  [ -n "$YAML_HOST" ] && DB_HOST="$YAML_HOST"
  [ -n "$YAML_PORT" ] && DB_PORT="$YAML_PORT"
  [ -n "$YAML_USER" ] && DB_USER="$YAML_USER"
  [ -n "$YAML_PASSWORD" ] && DB_PASSWORD="$YAML_PASSWORD"
  [ -n "$YAML_DATABASE" ] && DB_DATABASE="$YAML_DATABASE"
fi

# ============================================================
# 验证 mysql 客户端
# ============================================================
if [ "$DRY_RUN" = false ]; then
  if ! command -v mysql &>/dev/null; then
    echo "[ERROR] mysql 客户端未安装"
    echo "  macOS:  brew install mysql-client"
    echo "  Linux:  apt-get install mysql-client / yum install mysql"
    exit 1
  fi
fi

# ============================================================
# 收集要执行的 SQL 文件
# ============================================================
SQL_FILES=()

if [ -n "$SPECIFIC_FILE" ]; then
  # 指定单个文件
  TARGET="$MIGRATION_DIR/$SPECIFIC_FILE"
  if [ ! -f "$TARGET" ]; then
    echo "[ERROR] 指定的迁移文件不存在: $TARGET"
    exit 1
  fi
  SQL_FILES=("$TARGET")
else
  # 按文件名排序收集所有 .sql 文件
  while IFS= read -r f; do
    SQL_FILES+=("$f")
  done < <(find "$MIGRATION_DIR" -maxdepth 1 -name "*.sql" -type f | sort)

  # 如果指定了 --from，过滤掉编号小于指定值的文件
  if [ -n "$FROM_NUM" ]; then
    FILTERED=()
    for f in "${SQL_FILES[@]}"; do
      basename_f=$(basename "$f")
      # 提取文件名前缀数字 (例如 011_guardrails.sql -> 011)
      file_num=$(echo "$basename_f" | grep -oE '^[0-9]+' || echo "0")
      # 去除前导零进行数值比较
      file_num_int=$((10#$file_num))
      from_num_int=$((10#$FROM_NUM))
      if [ "$file_num_int" -ge "$from_num_int" ]; then
        FILTERED+=("$f")
      fi
    done
    SQL_FILES=("${FILTERED[@]}")
  fi
fi

if [ ${#SQL_FILES[@]} -eq 0 ]; then
  echo "[INFO] 没有找到需要执行的 SQL 迁移文件"
  exit 0
fi

# ============================================================
# 执行信息
# ============================================================
echo "============================================================"
echo "  DeepPool 数据库迁移"
echo "  数据库:   ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_DATABASE}"
echo "  迁移目录: ${MIGRATION_DIR}"
echo "  文件数量: ${#SQL_FILES[@]}"
if [ "$DRY_RUN" = true ]; then
echo "  模式:     DRY-RUN (仅预览)"
fi
echo "============================================================"
echo ""

# 列出将要执行的文件
echo "==> 迁移文件列表:"
for f in "${SQL_FILES[@]}"; do
  echo "    $(basename "$f")"
done
echo ""

# ============================================================
# Dry-run 模式：仅打印后退出
# ============================================================
if [ "$DRY_RUN" = true ]; then
  echo "[DRY-RUN] 以上文件将按顺序执行，实际未执行任何 SQL。"
  echo "          去掉 --dry-run 参数以实际执行。"
  exit 0
fi

# ============================================================
# 验证数据库连接
# ============================================================
echo "==> 验证数据库连接..."
MYSQL_CMD="mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} --database=${DB_DATABASE}"
if [ -n "$DB_PASSWORD" ]; then
  MYSQL_CMD="$MYSQL_CMD -p${DB_PASSWORD}"
fi

if ! $MYSQL_CMD -e "SELECT 1" &>/dev/null; then
  echo "[ERROR] 无法连接到数据库: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_DATABASE}"
  echo "  请检查连接参数是否正确"
  exit 1
fi
echo "    连接成功"
echo ""

# ============================================================
# 逐个执行 SQL 文件
# ============================================================
echo "==> 开始执行迁移..."
SUCCESS_COUNT=0
FAIL_COUNT=0

for f in "${SQL_FILES[@]}"; do
  filename=$(basename "$f")
  printf "    执行 %-45s" "$filename"

  if $MYSQL_CMD < "$f" 2>/tmp/deeppool_migration_err; then
    echo "✓"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    echo "✗"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "    [ERROR] $(cat /tmp/deeppool_migration_err)"
    echo ""
    echo "    迁移中断。请修复上述错误后重新执行："
    echo "    ./update_db.sh --config <config> --from $(echo "$filename" | grep -oE '^[0-9]+')"
    rm -f /tmp/deeppool_migration_err
    exit 1
  fi
done

rm -f /tmp/deeppool_migration_err

# ============================================================
# 执行摘要
# ============================================================
echo ""
echo "============================================================"
echo "  迁移完成!"
echo "  成功: ${SUCCESS_COUNT} 个文件"
if [ $FAIL_COUNT -gt 0 ]; then
echo "  失败: ${FAIL_COUNT} 个文件"
fi
echo "============================================================"
