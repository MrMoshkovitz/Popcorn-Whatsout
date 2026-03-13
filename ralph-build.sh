#!/usr/bin/env bash
# Ralph — Autonomous Popcorn Build System
# Runs Claude Code in a loop, executing tasks from master-plan.md until done.
# Usage: ./ralph-build.sh

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

MODEL="claude-opus-4-6"
PROMPT_FILE="ralph-prompt.md"
PLAN_FILE="master-plan.md"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/ralph-build.log"
STATE_FILE=".ralph-state"
LIMIT_FILE=".ralph-last-limit"

MAX_ITERATIONS=100
MAX_TURNS=100
CREDIT_RESET_SECONDS=14400    # 4 hours
BUFFER_SECONDS=300            # 5 minutes extra wait
CRASH_WAIT_SECONDS=60         # Wait after non-rate-limit crash
COMPLETION_MARKER="POPCORN BUILD COMPLETE"

# ═══════════════════════════════════════════════════════════════
# Logging & Display
# ═══════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

BAR_WIDTH=30
TASK_DURATIONS=()  # track per-task durations for ETA

timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log() {
    local msg="[$(timestamp)] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

log_info()    { log "${BLUE}INFO${NC}  $1"; }
log_success() { log "${GREEN}OK${NC}    $1"; }
log_warn()    { log "${YELLOW}WARN${NC}  $1"; }
log_error()   { log "${RED}ERROR${NC} $1"; }

# ═══════════════════════════════════════════════════════════════
# Progress Display
# ═══════════════════════════════════════════════════════════════

get_phase_name() {
    local task_id="$1"
    local phase_num="${task_id%%.*}"
    case "$phase_num" in
        0) echo "Infrastructure" ;;
        1) echo "Database" ;;
        2) echo "CSV Parser" ;;
        3) echo "TMDB API + Matcher" ;;
        4) echo "Engines" ;;
        5) echo "Dashboard" ;;
        6) echo "Telegram Bot" ;;
        7) echo "Cron + Docs" ;;
        8) echo "Integration Testing" ;;
        9) echo "Documentation + Polish" ;;
        10) echo "Definition of Done" ;;
        *) echo "Unknown" ;;
    esac
}

format_duration() {
    local secs="$1"
    if [[ $secs -ge 3600 ]]; then
        printf "%dh %dm" $((secs / 3600)) $(( (secs % 3600) / 60 ))
    elif [[ $secs -ge 60 ]]; then
        printf "%dm %ds" $((secs / 60)) $((secs % 60))
    else
        printf "%ds" "$secs"
    fi
}

calc_eta() {
    local remaining="$1"
    local count=${#TASK_DURATIONS[@]}

    if [[ $count -eq 0 ]]; then
        echo "calculating..."
        return
    fi

    local sum=0
    for d in "${TASK_DURATIONS[@]}"; do
        sum=$((sum + d))
    done
    local avg=$((sum / count))
    local eta_secs=$((avg * remaining))

    format_duration "$eta_secs"
}

show_progress() {
    local completed="$1"
    local remaining="$2"
    local failed="$3"
    local total="$4"
    local task_name="$5"
    local elapsed="$6"

    # Extract task ID (e.g., "Task 3.2" -> "3.2")
    local task_id
    task_id=$(echo "$task_name" | grep -oE '[0-9]+\.[0-9]+' | head -1)
    local phase_name
    phase_name=$(get_phase_name "$task_id")

    # Calculate percentage
    local pct=0
    if [[ $total -gt 0 ]]; then
        pct=$(( (completed * 100) / total ))
    fi

    # Build the bar: filled = green, empty = dim
    local filled=$(( (completed * BAR_WIDTH) / total ))
    local empty=$((BAR_WIDTH - filled))
    local bar=""
    for ((i = 0; i < filled; i++)); do bar+="█"; done
    for ((i = 0; i < empty; i++)); do bar+="░"; done

    local eta
    eta=$(calc_eta "$remaining")
    local elapsed_fmt
    elapsed_fmt=$(format_duration "$elapsed")

    echo ""
    echo -e "  ${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${GREEN}${bar}${NC}  ${BOLD}${pct}%${NC}  (${completed}/${total})"
    echo ""
    echo -e "  ${BOLD}Current:${NC}  ${YELLOW}${task_name}${NC}"
    echo -e "  ${BOLD}Phase:${NC}    ${MAGENTA}${phase_name}${NC} (Phase ${task_id%%.*})"
    echo ""
    echo -e "  ${GREEN}${completed} done${NC}  ${DIM}|${NC}  ${YELLOW}${remaining} left${NC}  ${DIM}|${NC}  ${RED}${failed} failed${NC}"
    echo -e "  ${DIM}Elapsed: ${elapsed_fmt}  |  ETA: ~${eta}${NC}"
    echo ""
    echo -e "  ${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════
# Startup Checks
# ═══════════════════════════════════════════════════════════════

startup_checks() {
    local fail=0

    if ! command -v claude &>/dev/null; then
        log_error "Claude Code CLI not found. Install it first."
        fail=1
    fi

    if ! git remote -v &>/dev/null; then
        log_warn "No git remote configured. Pushes will be skipped."
    fi

    if [[ ! -f "$PLAN_FILE" ]]; then
        log_error "$PLAN_FILE not found."
        fail=1
    fi

    if [[ ! -f "$PROMPT_FILE" ]]; then
        log_error "$PROMPT_FILE not found."
        fail=1
    fi

    mkdir -p "$LOG_DIR"

    if [[ $fail -eq 1 ]]; then
        log_error "Startup checks failed. Aborting."
        exit 2
    fi
}

# ═══════════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════════

show_banner() {
    local total remaining completed failed
    total=$(grep -c '### - \[' "$PLAN_FILE" 2>/dev/null || true)
    completed=$(grep -c '### - \[x\]' "$PLAN_FILE" 2>/dev/null || true)
    remaining=$(grep -c '### - \[ \]' "$PLAN_FILE" 2>/dev/null || true)
    failed=$(grep -c '### - \[!\]' "$PLAN_FILE" 2>/dev/null || true)

    echo -e "${BOLD}${CYAN}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║         RALPH BUILD SYSTEM v1.0          ║"
    echo "  ║      Autonomous Popcorn Builder          ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  Project:    ${BOLD}Popcorn — WhatsOut${NC}"
    echo -e "  Model:      ${BOLD}$MODEL${NC}"
    echo -e "  Max turns:  ${BOLD}$MAX_TURNS${NC} per iteration"
    echo -e "  Max iters:  ${BOLD}$MAX_ITERATIONS${NC}"
    echo ""
    echo -e "  Tasks:      ${GREEN}$completed done${NC} | ${YELLOW}$remaining remaining${NC} | ${RED}$failed failed${NC} | $total total"
    echo ""
    echo -e "  Log:        $LOG_FILE"
    echo -e "  Started:    $(timestamp)"
    echo ""
}

# ═══════════════════════════════════════════════════════════════
# Credit Exhaustion Detection
# ═══════════════════════════════════════════════════════════════

is_credit_exhausted() {
    local output="$1"
    local exit_code="$2"
    local duration="$3"

    # Check output for rate limit signals
    if echo "$output" | grep -qiE 'rate.limit|429|too.many.request|quota.exceed|usage.limit|capacity|overloaded|503|credit'; then
        return 0
    fi

    # Fast failure (< 30s) with non-zero exit = likely rate limit
    if [[ $exit_code -ne 0 && $duration -lt 30 ]]; then
        return 0
    fi

    return 1
}

# ═══════════════════════════════════════════════════════════════
# Smart Wait (credit reset)
# ═══════════════════════════════════════════════════════════════

smart_wait() {
    local consecutive_limits="${1:-1}"
    local now wait_seconds last_limit time_since

    now=$(date +%s)

    # Base wait = credit reset + buffer
    wait_seconds=$((CREDIT_RESET_SECONDS + BUFFER_SECONDS))

    # If we have a previous limit timestamp, calculate remaining wait
    if [[ -f "$LIMIT_FILE" ]]; then
        last_limit=$(cat "$LIMIT_FILE")
        time_since=$((now - last_limit))

        if [[ $time_since -ge $CREDIT_RESET_SECONDS ]]; then
            # Credits should have reset — try a short wait (transient issue)
            log_info "Credits should have reset (${time_since}s ago). Waiting 60s for transient issue."
            countdown 60
            return
        fi

        # Calculate remaining wait
        wait_seconds=$((CREDIT_RESET_SECONDS - time_since + BUFFER_SECONDS))
    fi

    # Exponential backoff for repeated hits
    if [[ $consecutive_limits -ge 3 ]]; then
        local extra=$(( (consecutive_limits - 2) * 3600 ))
        # Cap at 6 hours total
        local max_extra=$((6 * 3600 - CREDIT_RESET_SECONDS))
        if [[ $extra -gt $max_extra ]]; then
            extra=$max_extra
        fi
        wait_seconds=$((wait_seconds + extra))
    fi

    # Record this limit hit
    echo "$now" > "$LIMIT_FILE"

    local hours=$((wait_seconds / 3600))
    local mins=$(( (wait_seconds % 3600) / 60 ))
    log_warn "Credit exhaustion detected. Waiting ${hours}h ${mins}m for reset."

    countdown "$wait_seconds"
}

countdown() {
    local remaining="$1"
    local interval=60

    while [[ $remaining -gt 0 ]]; do
        local hours=$((remaining / 3600))
        local mins=$(( (remaining % 3600) / 60 ))
        local secs=$((remaining % 60))
        printf "\r  Resuming in %02d:%02d:%02d " "$hours" "$mins" "$secs"

        if [[ $remaining -lt $interval ]]; then
            sleep "$remaining"
            remaining=0
        else
            sleep "$interval"
            remaining=$((remaining - interval))
        fi
    done
    echo ""
}

# ═══════════════════════════════════════════════════════════════
# State Management
# ═══════════════════════════════════════════════════════════════

save_state() {
    local iteration="$1"
    local status="$2"
    local tmp="${STATE_FILE}.tmp"

    cat > "$tmp" <<EOF
iteration=$iteration
status=$status
timestamp=$(timestamp)
EOF
    mv "$tmp" "$STATE_FILE"
}

get_next_task_name() {
    grep -m1 '### - \[ \] Task' "$PLAN_FILE" 2>/dev/null | sed 's/### - \[ \] //' || echo "unknown"
}

# ═══════════════════════════════════════════════════════════════
# Cleanup Handler
# ═══════════════════════════════════════════════════════════════

cleanup() {
    echo ""
    log_warn "Interrupted. Saving state..."

    local completed remaining
    completed=$(grep -c '### - \[x\]' "$PLAN_FILE" 2>/dev/null || true)
    remaining=$(grep -c '### - \[ \]' "$PLAN_FILE" 2>/dev/null || true)

    save_state "$iteration" "interrupted"
    log_info "Final state: $completed completed, $remaining remaining, iteration $iteration"
    log_info "Resume by running: ./ralph-build.sh"

    exit 130
}

trap cleanup SIGINT SIGTERM

# ═══════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════

main() {
    startup_checks
    show_banner

    # Confirmation prompt (skip with RALPH_AUTO=1)
    if [[ "${RALPH_AUTO:-0}" != "1" ]]; then
        echo -e "  ${BOLD}Press Enter to start building, or Ctrl+C to abort.${NC}"
        read -r
    fi

    log_info "Ralph build started"
    log_info "═══════════════════════════════════════════"

    local iteration=1
    local consecutive_limits=0
    local build_start
    build_start=$(date +%s)

    while true; do
        # Count tasks
        local remaining completed failed
        remaining=$(grep -c '### - \[ \]' "$PLAN_FILE" 2>/dev/null || true)
        completed=$(grep -c '### - \[x\]' "$PLAN_FILE" 2>/dev/null || true)
        failed=$(grep -c '### - \[!\]' "$PLAN_FILE" 2>/dev/null || true)

        # Sanity check: if plan file looks corrupted (no checkboxes at all)
        local any_tasks
        any_tasks=$(grep -c '### - \[' "$PLAN_FILE" 2>/dev/null || true)
        if [[ $any_tasks -eq 0 ]]; then
            log_error "master-plan.md appears corrupted (no task markers found). Restoring from git..."
            git checkout HEAD -- "$PLAN_FILE"
            remaining=$(grep -c '\- \[ \]' "$PLAN_FILE" 2>/dev/null || true)
            if [[ $any_tasks -eq 0 ]]; then
                log_error "Could not restore master-plan.md. Aborting."
                exit 2
            fi
        fi

        # All tasks done
        if [[ $remaining -eq 0 ]]; then
            local build_end build_duration total_fmt
            build_end=$(date +%s)
            build_duration=$((build_end - build_start))
            total_fmt=$(format_duration "$build_duration")

            # Final full progress bar
            show_progress "$completed" "0" "$failed" "$((completed + failed))" "ALL TASKS COMPLETE" "$build_duration"

            log_success "═══════════════════════════════════════════"
            log_success "BUILD COMPLETE"
            log_success "═══════════════════════════════════════════"
            log_success "Tasks completed: $completed"
            log_success "Tasks failed:    $failed"
            log_success "Iterations:      $((iteration - 1))"
            log_success "Total time:      $total_fmt"
            echo ""

            # Show recent commits
            log_info "Recent commits:"
            git log --oneline -30 2>/dev/null | while read -r line; do
                log_info "  $line"
            done

            # Run tests if they exist
            if [[ -d "tests" ]] && ls tests/test_*.py &>/dev/null; then
                log_info "Running test suite..."
                python -m pytest tests/ -v 2>&1 | tee -a "$LOG_FILE" || true
            fi

            save_state "$iteration" "complete"
            exit 0
        fi

        # Max iterations guard
        if [[ $iteration -gt $MAX_ITERATIONS ]]; then
            log_error "Max iterations ($MAX_ITERATIONS) reached. $remaining tasks remaining."
            save_state "$iteration" "max_iterations"
            exit 1
        fi

        # Get next task name for logging
        local task_name total
        task_name=$(get_next_task_name)
        total=$(grep -c '### - \[' "$PLAN_FILE" 2>/dev/null || true)

        # Show progress bar
        local elapsed_so_far=$(( $(date +%s) - build_start ))
        show_progress "$completed" "$remaining" "$failed" "$total" "$task_name" "$elapsed_so_far"

        log_info "Iteration $iteration | Next: $task_name"

        save_state "$iteration" "running"

        # Run Claude Code
        local start_time end_time duration exit_code output
        start_time=$(date +%s)

        set +e
        output=$(claude --model "$MODEL" \
            --dangerously-skip-permissions \
            --max-turns "$MAX_TURNS" \
            --verbose \
            -p "$(cat "$PROMPT_FILE")" 2>&1)
        exit_code=$?
        set -e

        end_time=$(date +%s)
        duration=$((end_time - start_time))

        local dur_fmt
        dur_fmt=$(format_duration "$duration")
        log_info "CC finished in ${dur_fmt} (exit code: $exit_code)"

        # Check for completion marker
        if echo "$output" | grep -qF "$COMPLETION_MARKER"; then
            # Re-enter the loop — the remaining count check at top will handle success
            log_success "Completion marker detected."
            consecutive_limits=0
            iteration=$((iteration + 1))
            continue
        fi

        # Check for credit exhaustion
        if is_credit_exhausted "$output" "$exit_code" "$duration"; then
            consecutive_limits=$((consecutive_limits + 1))
            log_warn "Credit exhaustion detected (hit #$consecutive_limits)"
            smart_wait "$consecutive_limits"
            # Don't increment iteration — retry the same task
            continue
        fi

        # Reset consecutive limits on successful run
        consecutive_limits=0

        # Check for BUILD HALTED (must be an actual heading, not inside a code block example)
        if grep -qE '^## BUILD HALTED' "$PLAN_FILE" 2>/dev/null; then
            log_error "BUILD HALTED marker found in master-plan.md."
            log_error "3+ consecutive tasks failed. Human review needed."
            save_state "$iteration" "halted"
            exit 2
        fi

        # Check for non-rate-limit crash
        if [[ $exit_code -ne 0 ]]; then
            log_warn "CC exited with code $exit_code (not rate limit). Waiting ${CRASH_WAIT_SECONDS}s before retry."
            sleep "$CRASH_WAIT_SECONDS"
            # Still increment — if CC crashed but may have committed work, next iteration re-checks
        else
            # Track successful task duration for ETA calculation
            TASK_DURATIONS+=("$duration")
        fi

        iteration=$((iteration + 1))
    done
}

# ═══════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════

main "$@"
