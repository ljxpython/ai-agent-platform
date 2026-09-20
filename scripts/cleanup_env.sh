#!/usr/bin/env bash
# ==============================================================================
# cleanup_env.sh - Agent 平台数据、日志、测试产物清理脚本
#
# 默认仅清理日志和缓存；控制面流水须显式选择并确认数据库。
# SQLite、备份、Runtime 数据库和测试库不自动删除。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 独立历史模式：仅执行明确选中的数据库操作，默认预览，执行前自动备份。
if [[ "${1:-}" == "--history" ]]; then
    shift
    cd "$ROOT_DIR/apps/platform-api"
    exec uv run --frozen python "scripts/cleanup_history.py" "$@"
fi

CLEAN_RUNTIME_DATA=false
DRY_RUN=false
ASSUME_YES=false
CLEAN_PLATFORM_LEDGERS=false
CONFIRM_DATABASE=""
WRITERS_STOPPED=false
KEEP_PROJECT=""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    printf "${BLUE}[INFO]${NC} %s\n" "$*"
}

log_success() {
    printf "${GREEN}[SUCCESS]${NC} %s\n" "$*"
}

log_warn() {
    printf "${YELLOW}[WARN]${NC} %s\n" "$*"
}

log_err() {
    printf "${RED}[ERROR]${NC} %s\n" "$*" >&2
}

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

清理本地日志与缓存。数据库流水为单独可选操作，源库与备份始终保留。

OPTIONS:
    --history [OPTIONS]         独立历史清理入口（必须首参数；--history --help 查看选项）
    -y, --yes                   跳过交互式二次确认，直接执行
    --include-runtime           清理旧 .runtime 工作区（不包含配置的外部工作区；要求停写）
    --keep-project UUID         独立模式：仅软删除其他项目，保留指定活动项目及全部历史数据
    --platform-ledgers          选择控制面 run_requests / audit_logs
    --confirm-database NAME     显式确认控制面数据库名
    --writers-stopped           确认已停止全部数据库写入方
    --dry-run                   仅扫描并输出待清理项与占用空间，不实际执行删除
    -h, --help                  显示帮助信息

示例:
    # 默认安全模式：交互确认，不清理 .runtime 沙箱产物
    ./scripts/cleanup_env.sh

    # 仅查看哪些可以清理，不进行任何删除
    ./scripts/cleanup_env.sh --dry-run

    # 包含 .runtime 沙箱数据一起清理
    ./scripts/cleanup_env.sh --include-runtime
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes)
            ASSUME_YES=true
            shift
            ;;
        --platform-ledgers)
            CLEAN_PLATFORM_LEDGERS=true
            shift
            ;;
        --keep-project)
            [[ $# -ge 2 && -n "$2" ]] || { log_err "缺少保留项目 UUID"; exit 2; }
            KEEP_PROJECT="$2"
            shift 2
            ;;
        --confirm-database)
            [[ $# -ge 2 ]] || { log_err "缺少数据库名"; exit 2; }
            CONFIRM_DATABASE="$2"
            shift 2
            ;;
        --writers-stopped)
            WRITERS_STOPPED=true
            shift
            ;;
        --include-runtime)
            CLEAN_RUNTIME_DATA=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_err "未知参数: $1"
            exit 2
            ;;
    esac
done

# 独立项目模式不顺带清理文件或流水；目标以 UUID 指定，避免同名误判。
if [[ -n "$KEEP_PROJECT" ]]; then
    [[ "$CLEAN_PLATFORM_LEDGERS" == "false" && "$CLEAN_RUNTIME_DATA" == "false" ]] || {
        log_err "--keep-project 不能和其他数据清理模式组合"; exit 2;
    }
    project_args=(clean-projects --keep-project "$KEEP_PROJECT")
    (cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/database.py "${project_args[@]}")
    [[ "$DRY_RUN" == "false" ]] || exit 0
    [[ -n "$CONFIRM_DATABASE" ]] || { log_err "需要 --confirm-database NAME；执行前请备份"; exit 2; }
    if [[ "$ASSUME_YES" == "false" ]]; then
        read -r -p "确认软删除除保留项目以外的所有项目？(y/N): " confirm
        [[ "$confirm" == [yY] || "$confirm" == [yY][eE][sS] ]] || exit 0
    fi
    (cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/database.py "${project_args[@]}" --execute --confirm-database "$CONFIRM_DATABASE")
    exit 0
fi

if [[ "$CLEAN_RUNTIME_DATA" == "true" && "$DRY_RUN" == "false" && "$WRITERS_STOPPED" == "false" ]]; then
    log_err "旧 Runtime 工作区清理也需要 --writers-stopped；外部工作区不在本脚本清理范围内"
    exit 2
fi

echo "================================================================="
echo "        AI Agent Platform 环境与数据一键清理工具"
echo "================================================================="
log_info "工程根目录: ${ROOT_DIR}"
log_info "清理 .runtime 沙箱数据: $([[ "$CLEAN_RUNTIME_DATA" == "true" ]] && echo "是" || echo "否 (受保护)")"
log_info "演练模式 (Dry-Run): $([[ "$DRY_RUN" == "true" ]] && echo "是" || echo "否")"
echo "-----------------------------------------------------------------"

# 1. 扫描文件系统待清理项
scan_files() {
    log_info "正在扫描待清理的文件与缓存..."

    log_info "SQLite 源库和所有数据库备份受保护，不纳入清理。"

    # Playwright 日志
    PLAYWRIGHT_LOGS=()
    if [[ -d "${ROOT_DIR}/.playwright-cli" ]]; then
        while IFS= read -r -d '' file; do
            PLAYWRIGHT_LOGS+=("$file")
        done < <(find "${ROOT_DIR}/.playwright-cli" -name "*.log" -print0 2>/dev/null || true)
    fi

    # 测试与构建缓存目录
    CACHE_DIRS=(
        "${ROOT_DIR}/.pytest_cache"
        "${ROOT_DIR}/.ruff_cache"
        "${ROOT_DIR}/.mypy_cache"
        "${ROOT_DIR}/apps/platform-api/.pytest_cache"
        "${ROOT_DIR}/apps/platform-api/.ruff_cache"
        "${ROOT_DIR}/apps/runtime-service/.pytest_cache"
        "${ROOT_DIR}/apps/runtime-service/.ruff_cache"
        "${ROOT_DIR}/test-results"
        "${ROOT_DIR}/apps/platform-web/test-results"
    )

    printf "  • 发现 Playwright 控制台日志: %d 个\n" "${#PLAYWRIGHT_LOGS[@]}"
    for directory in "${CACHE_DIRS[@]}"; do
        [[ ! -d "$directory" ]] || du -sh "$directory"
    done
    log_info "测试报告仅删除 Git 未跟踪文件，已跟踪文件保留。"
    git -C "$ROOT_DIR" clean -ndx -- test-results apps/platform-web/test-results

    if [[ "$CLEAN_RUNTIME_DATA" == "true" ]]; then
        if [[ -d "${ROOT_DIR}/apps/runtime-service/.runtime" ]]; then
            printf "  • 发现 Runtime 运行沙箱目录: apps/runtime-service/.runtime (约 $(du -sh "${ROOT_DIR}/apps/runtime-service/.runtime" | cut -f1))\n"
        fi
    fi
}

scan_files

platform_ledgers() {
    (cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/database.py clean-ledgers "$@")
}

if [[ "$CLEAN_PLATFORM_LEDGERS" == "true" ]]; then
    platform_ledgers
    if [[ "$DRY_RUN" != "true" ]]; then
        [[ "$WRITERS_STOPPED" == "true" && -n "$CONFIRM_DATABASE" ]] || {
            log_err "数据库清理需要 --writers-stopped 和 --confirm-database NAME"; exit 2;
        }
    fi
fi

if [[ "$DRY_RUN" == "true" ]]; then
    log_info "当前为 Dry-Run 演练模式，扫描完成，退出。"
    exit 0
fi

if [[ "$ASSUME_YES" == "false" ]]; then
    echo "-----------------------------------------------------------------"
    read -r -p "⚠️  确认要开始清理以上数据和数据库会话吗？(y/N): " confirm
    if [[ "$confirm" != [yY] && "$confirm" != [yY][eE][sS] ]]; then
        log_warn "用户取消操作，未做任何修改。"
        exit 0
    fi
fi

echo "================================================================="
log_info "开始执行清理工作..."

# 控制面流水单独选择，不触碰 Runtime/测试数据库及迁移备份。
if [[ "$CLEAN_PLATFORM_LEDGERS" == "true" ]]; then
    platform_ledgers --execute --writers-stopped --confirm-database "$CONFIRM_DATABASE"
fi

# 5. 清理 Playwright 日志与测试报告
clean_logs_and_reports() {
    log_info "清理 Playwright 日志与测试报告目录..."
    if [[ -d "${ROOT_DIR}/.playwright-cli" ]]; then
        find "${ROOT_DIR}/.playwright-cli" -name "*.log" -delete 2>/dev/null || true
    fi
    git -C "$ROOT_DIR" clean -fdx -- test-results apps/platform-web/test-results
    log_success "测试日志与测试报告已清理。"
}

clean_logs_and_reports

# 6. 清理 Python 与构建工具缓存
clean_caches() {
    log_info "清理 .pytest_cache / .ruff_cache / .mypy_cache 等缓存目录..."
    rm -rf "${ROOT_DIR}/.pytest_cache" \
           "${ROOT_DIR}/.ruff_cache" \
           "${ROOT_DIR}/.mypy_cache" \
           "${ROOT_DIR}/apps/platform-api/.pytest_cache" \
           "${ROOT_DIR}/apps/platform-api/.ruff_cache" \
           "${ROOT_DIR}/apps/runtime-service/.pytest_cache" \
           "${ROOT_DIR}/apps/runtime-service/.ruff_cache"
    log_success "构建与分析缓存清理完毕。"
}

clean_caches

# 7. Runtime 沙箱工作区清理（按参数决定）
clean_runtime_workspaces() {
    if [[ "$CLEAN_RUNTIME_DATA" == "true" ]]; then
        log_info "清理 apps/runtime-service/.runtime/ 沙箱工作区文件..."
        rm -rf "${ROOT_DIR}/apps/runtime-service/.runtime/workspaces"/* \
               "${ROOT_DIR}/apps/runtime-service/.runtime/showcase"/*
        log_success "apps/runtime-service/.runtime/ 沙箱工作区已清空。"
    else
        log_info "根据指示，本次跳过清理 apps/runtime-service/.runtime/ 数据。"
    fi
}

clean_runtime_workspaces

echo "================================================================="
log_success "🎉 一键环境与数据清理圆满完成！"
echo "================================================================="
