#!/usr/bin/env bash
# ==============================================================================
# cleanup_env.sh - Agent 平台数据、日志、测试产物清理与测试环境重置工具
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 优先使用与服务端匹配的 PostgreSQL 17 工具链
if [[ -d "/usr/local/opt/postgresql@17/bin" ]]; then
    export PATH="/usr/local/opt/postgresql@17/bin:$PATH"
    export PG_BIN="/usr/local/opt/postgresql@17/bin"
elif [[ -d "/opt/homebrew/opt/postgresql@17/bin" ]]; then
    export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
    export PG_BIN="/opt/homebrew/opt/postgresql@17/bin"
fi

# 独立历史模式：仅执行明确选中的底层数据库操作
if [[ "${1:-}" == "--history" ]]; then
    shift
    cd "$ROOT_DIR/apps/platform-api"
    exec uv run --frozen python "scripts/cleanup_history.py" "$@"
fi


CLEAN_RUNTIME_DATA=false
CLEAN_TEST_ENV=false
DRY_RUN=false
ASSUME_YES=false
CLEAN_PLATFORM_LEDGERS=false
CONFIRM_DATABASE=""
WRITERS_STOPPED=false
KEEP_PROJECT=""
KEEP_PROJECT_NAME=""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
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
    echo -e "${BOLD}AI Agent Platform 环境与数据清理工具${NC}

${BOLD}用法:${NC}
    $(basename "$0") [模式 / 选项]

${BOLD}常用模式 (人话指南):${NC}
    ${GREEN}1. 日常快速清理 (零风险，仅清日志与编译缓存)${NC}
       ./scripts/cleanup_env.sh
       ./scripts/cleanup_env.sh --dry-run             # 仅预览待清理项

    ${GREEN}2. 测试环境一键重置 (删除测试产物与对话，保留模型/记忆/技能/用户/指定项目)${NC}
       # 演练预览：查看沙箱文件、将清空的对话数以及将软删除的项目
       ./scripts/cleanup_env.sh --clean-test-env --keep-project-name Test --dry-run

       # 真正执行一键重置 (默认保留 'Test' 项目，其余软删除；清空沙箱与用户对话数据)
       ./scripts/cleanup_env.sh --clean-test-env --keep-project-name Test

${BOLD}参数详情:${NC}
    ${BOLD}[测试环境重置]${NC}
    --clean-test-env            一键清理测试环境：沙箱文件 + 数据库对话快照 + 软删除多余项目
    --keep-project-name NAME    重置时保留的活跃项目名称 (大小写不敏感，默认: Test)
    --keep-project UUID         重置时保留的活跃项目 UUID

    ${BOLD}[细粒度底层选项]${NC}
    --include-runtime           单独清理 .runtime 沙箱临时工作区文件 (需停写)
    --platform-ledgers          单独清空控制面请求历史与审计流水 (run_requests / audit_logs)
    --history [OPTIONS]         底层高级历史清理入口 (调用 cleanup_history.py)
    --writers-stopped           声明已停止后端写进程 (如已执行 local-stack.sh stop)
    --confirm-database NAME     显式确认控制面数据库名
    -y, --yes                   跳过交互式提示，自动确认执行
    --dry-run                   仅扫描并输出待清理项与占用空间，不实际执行删除
    -h, --help                  显示本帮助文档

${BOLD}安全保护保证:${NC}
    • 无论何种模式，${BOLD}模型配置、长期记忆 (dear_memories)、技能 (dear_skills)、用户数据${NC} 坚决保留。
    • 真实数据库截断前会自动执行 pg_dump 备份到 apps/platform-api/.data/backups/。"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --clean-test-env)
            CLEAN_TEST_ENV=true
            CLEAN_RUNTIME_DATA=true
            shift
            ;;
        --keep-project-name)
            [[ $# -ge 2 && -n "$2" ]] || { log_err "缺少保留项目名称"; exit 2; }
            KEEP_PROJECT_NAME="$2"
            shift 2
            ;;
        --keep-project)
            [[ $# -ge 2 && -n "$2" ]] || { log_err "缺少保留项目 UUID"; exit 2; }
            KEEP_PROJECT="$2"
            shift 2
            ;;
        -y|--yes)
            ASSUME_YES=true
            shift
            ;;
        --platform-ledgers)
            CLEAN_PLATFORM_LEDGERS=true
            shift
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

# 获取数据库名辅助函数
get_databases() {
    local info
    info="$(cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/database.py check 2>/dev/null || true)"
    PLATFORM_DB_NAME="$(echo "$info" | grep -o '"database": "[^"]*' | cut -d'"' -f4 || true)"

    RUNTIME_DB_NAME=""
    if [[ -f "$ROOT_DIR/apps/runtime-service/.env" ]]; then
        local rt_uri
        rt_uri="$(grep -E '^DATABASE_URI=' "$ROOT_DIR/apps/runtime-service/.env" | cut -d= -f2- | tr -d '"'\'' ' || true)"
        RUNTIME_DB_NAME="${rt_uri##*/}"
        RUNTIME_DB_NAME="${RUNTIME_DB_NAME%%\?*}"
    fi
}

# 1. 扫描文件系统待清理项
scan_files() {
    log_info "正在扫描待清理的文件与缓存..."
    log_info "PostgreSQL 源库配置、数据库备份受保护，不纳入物理删除。"

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

    if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        log_info "测试报告仅删除 Git 未跟踪文件，已跟踪文件保留。"
        git -C "$ROOT_DIR" clean -ndx -- test-results apps/platform-web/test-results 2>/dev/null || true
    fi

    if [[ "$CLEAN_RUNTIME_DATA" == "true" ]]; then
        if [[ -d "${ROOT_DIR}/apps/runtime-service/.runtime" ]]; then
            printf "  • 发现 Runtime 运行沙箱目录: apps/runtime-service/.runtime (约 $(du -sh "${ROOT_DIR}/apps/runtime-service/.runtime" 2>/dev/null | cut -f1 || echo '0B'))\n"
        fi
    fi
}

# 2. 清理日志与测试报告
clean_logs_and_reports() {
    log_info "清理 Playwright 日志与测试报告目录..."
    if [[ -d "${ROOT_DIR}/.playwright-cli" ]]; then
        find "${ROOT_DIR}/.playwright-cli" -name "*.log" -delete 2>/dev/null || true
    fi
    if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git -C "$ROOT_DIR" clean -fdx -- test-results apps/platform-web/test-results 2>/dev/null || true
    else
        rm -rf "${ROOT_DIR}/test-results" "${ROOT_DIR}/apps/platform-web/test-results"
    fi
    log_success "测试日志与测试报告已清理。"
}

# 3. 清理构建工具缓存
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

# 4. 清理沙箱
clean_runtime_workspaces() {
    if [[ "$CLEAN_RUNTIME_DATA" == "true" ]]; then
        log_info "清理 apps/runtime-service/.runtime/ 沙箱工作区文件..."
        if [[ -d "${ROOT_DIR}/apps/runtime-service/.runtime/workspaces" ]]; then
            rm -rf "${ROOT_DIR}/apps/runtime-service/.runtime/workspaces"/* 2>/dev/null || true
        fi
        if [[ -d "${ROOT_DIR}/apps/runtime-service/.runtime/showcase" ]]; then
            rm -rf "${ROOT_DIR}/apps/runtime-service/.runtime/showcase"/* 2>/dev/null || true
        fi
        log_success "apps/runtime-service/.runtime/ 沙箱工作区已清空。"
    fi
}

# ==============================================================================
# 模式 A: 一键测试环境重置 (--clean-test-env)
# ==============================================================================
if [[ "$CLEAN_TEST_ENV" == "true" ]]; then
    target_project_name="${KEEP_PROJECT_NAME:-${KEEP_PROJECT:-Test}}"
    echo "================================================================="
    echo "        AI Agent Platform 测试环境一键重置与数据清理"
    echo "================================================================="
    log_info "保留目标活跃项目: ${BOLD}${target_project_name}${NC} (其余历史项目将软删除)"
    log_info "清理用户对话快照: ${BOLD}是 (Checkpoints, Runs, Threads, Events, Inbox)${NC}"
    log_info "清理沙箱工作区:   ${BOLD}是 (apps/runtime-service/.runtime/workspaces & showcase)${NC}"
    log_info "保护项:           ${GREEN}模型配置、长期记忆(dear_memories)、技能(dear_skills)、用户账户与凭证${NC}"
    log_info "演练模式 (Dry-Run): $([[ "$DRY_RUN" == "true" ]] && echo "是" || echo "否")"
    echo "-----------------------------------------------------------------"

    get_databases
    [[ -n "$PLATFORM_DB_NAME" ]] || { log_err "无法检测到 Platform API 数据库连接"; exit 2; }
    [[ -n "$RUNTIME_DB_NAME" ]] || { log_err "无法检测到 Runtime Service 数据库连接"; exit 2; }

    log_info "检测到控制面数据库: ${PLATFORM_DB_NAME}"
    log_info "检测到运行时数据库: ${RUNTIME_DB_NAME}"

    scan_files

    # 1. 预览/检查要保留的项目
    log_info "正在检查项目表并准备软删除多余项目..."
    project_cli_args=(clean-projects)
    if [[ -n "$KEEP_PROJECT" ]]; then
        project_cli_args+=(--keep-project "$KEEP_PROJECT")
    else
        project_cli_args+=(--keep-project-name "$target_project_name")
    fi
    (cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/database.py "${project_cli_args[@]}")

    # 2. 预览待清空的运行时对话快照
    log_info "正在扫描运行时对话快照与执行记录..."
    (cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/cleanup_history.py --runtime --cancel-unfinished-runs --dry-run)

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "-----------------------------------------------------------------"
        log_info "当前为 Dry-Run 演练模式，上述项未做任何更改，退出。"
        exit 0
    fi

    # 二次确认
    if [[ "$ASSUME_YES" == "false" ]]; then
        echo "-----------------------------------------------------------------"
        echo -e "${YELLOW}⚠️  警告：该操作将清空用户历史对话、截断 Checkpoints 并软删除其他项目！${NC}"
        echo -e "${YELLOW}   (长期记忆、技能库、模型参数与用户信息将得到完整保留)${NC}"
        read -r -p "确认开始执行重置操作吗？(y/N): " confirm
        if [[ "$confirm" != [yY] && "$confirm" != [yY][eE][sS] ]]; then
            log_warn "用户取消操作，未做任何修改。"
            exit 0
        fi
    fi

    echo "================================================================="
    log_info "开始执行测试环境重置..."

    # 软删除非保留项目
    log_info "正在执行项目软删除..."
    (cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/database.py "${project_cli_args[@]}" --execute --confirm-database "$PLATFORM_DB_NAME")

    # 执行会话与快照清空 (内部自动调用 pg_dump 备份并取消挂死的 runs)
    log_info "正在清空对话快照与运行记录 (自动创建目标库备份)..."
    (cd "$ROOT_DIR/apps/platform-api" && uv run --frozen python scripts/cleanup_history.py --runtime --cancel-unfinished-runs --execute --writers-stopped --confirm-database "$RUNTIME_DB_NAME")

    # 清理沙箱临时文件
    clean_runtime_workspaces

    # 清理测试报告与缓存
    clean_logs_and_reports
    clean_caches

    echo "================================================================="
    log_success "🎉 测试环境重置圆满完成！仅保留项目 '${target_project_name}'，沙箱与对话数据已彻底清空！"
    echo "================================================================="
    exit 0
fi

# ==============================================================================
# 模式 B: 独立单项项目保留模式 (--keep-project)
# ==============================================================================
if [[ -n "$KEEP_PROJECT" || -n "$KEEP_PROJECT_NAME" ]]; then
    [[ "$CLEAN_PLATFORM_LEDGERS" == "false" && "$CLEAN_RUNTIME_DATA" == "false" ]] || {
        log_err "--keep-project / --keep-project-name 单独使用时不能和其他数据清理模式组合"; exit 2;
    }
    project_args=(clean-projects)
    if [[ -n "$KEEP_PROJECT" ]]; then
        project_args+=(--keep-project "$KEEP_PROJECT")
    else
        project_args+=(--keep-project-name "$KEEP_PROJECT_NAME")
    fi

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

# ==============================================================================
# 模式 C: 默认快速清理模式 (日志与缓存)
# ==============================================================================
echo "================================================================="
echo "        AI Agent Platform 环境与数据一键清理工具"
echo "================================================================="
log_info "工程根目录: ${ROOT_DIR}"
log_info "清理 .runtime 沙箱数据: $([[ "$CLEAN_RUNTIME_DATA" == "true" ]] && echo "是" || echo "否 (受保护)")"
log_info "演练模式 (Dry-Run): $([[ "$DRY_RUN" == "true" ]] && echo "是" || echo "否")"
echo "-----------------------------------------------------------------"

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
    read -r -p "⚠️  确认要开始清理以上测试产物与缓存吗？(y/N): " confirm
    if [[ "$confirm" != [yY] && "$confirm" != [yY][eE][sS] ]]; then
        log_warn "用户取消操作，未做任何修改。"
        exit 0
    fi
fi

echo "================================================================="
log_info "开始执行清理工作..."

if [[ "$CLEAN_PLATFORM_LEDGERS" == "true" ]]; then
    platform_ledgers --execute --writers-stopped --confirm-database "$CONFIRM_DATABASE"
fi

clean_logs_and_reports
clean_caches
clean_runtime_workspaces

echo "================================================================="
log_success "🎉 一键环境与数据清理圆满完成！"
echo "================================================================="
