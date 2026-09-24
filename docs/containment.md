# Containment design for the deliberately vulnerable code

**Status:** APPROVED at gate G2 on 2026-09-24, with `systemd-run` on the Pi. The vulnerable shell path (plan P2.1) is not written until the containment battery in section 5 passes on the laptop. It implements decision D12 and the conditions in [ethics/LAB_ONLY.md](../ethics/LAB_ONLY.md).

## 1. What has to be contained

| Sink | Where | Can run commands? |
|---|---|---|
| String-built SQL against SQLite | Tier 1, Tier 2 (second-order query) | No. Through `execute()` a string cannot stack a statement, load an extension or `ATTACH` a file ([E-012](evidence/LOG.md)). Injection stays inside the database. |
| String-built shell command | Tier 1 audit step | **Yes.** This is the one sink the sandbox exists for. |
| String-formatted log lines | Tier 2 | No, only file content. |
| Agent tool stubs | Tier 3 | No. The stubs only append to a log. |

So the sandbox must hold one thing: a command string built from decoded, attacker-influenced text and passed to a shell. Constraints that follow for the code, enforced by tests in P2: the vulnerable handler uses `execute()` and never `executescript()`; the shell step runs a fixed inert template, an `echo` that appends the identifier to an audit file, into which the payload is concatenated; and nothing else in the tier calls a shell.

## 2. What the sandbox is for, and what it is not

It should ensure that a payload (ours, or one that is wrong by mistake) cannot: reach the network; read or change anything outside the sandbox's own directories; persist after the run; use unbounded CPU, memory or processes; or gain privileges.

It is not a defense against a kernel or container-runtime exploit, or against a skilled hostile payload author. The payloads are the author's own and canary-only (plan section 6), and the payload set is reviewed at gate G5. The sandbox limits the blast radius of a mistake.

## 3. Laptop: Docker

A separate `vtb-sandbox` image (same Bookworm base as the dev image, Python and the tier code only, no build tools) run with:

| Setting | Effect |
|---|---|
| `--network none` | no network interface except loopback |
| `--read-only` | root filesystem cannot be written |
| `--user 10001:10001` | not root; no login, no sudo |
| `--cap-drop ALL` and `--security-opt no-new-privileges` | no capabilities, and none can be gained through setuid programs |
| `--pids-limit 64`, `--memory 256m`, `--cpus 1` | bounded processes, memory and CPU |
| `--tmpfs /tmp` (mode 1777) and `--tmpfs /audit` (owned by the sandbox user), both `noexec,nosuid` and size-capped | scratch space that vanishes with the container |
| one bind mount, `/canary`, a per-run empty directory owned by the harness | the only place a payload's side effect can persist, and the only thing the harness reads back |
| no other mounts, no Docker socket, no environment variables passed in | nothing of the host or its secrets is visible |

Every call is a fresh `docker run`, not an `exec` into a long-lived container, so nothing can carry over between calls (oracle principle 2) and the golden database is copied in at the start of each call. The harness talks to the tier over stdin and stdout, never a network port, and reads what a payload left in `/canary` from the host side of the mount. Output is capped at 1 MiB per stream, and a timeout removes the container itself. The runner is `harness/sandbox.py`; its flags are pinned by `tests/test_sandbox_flags.py`.

## 4. Pi: no Docker on the measurement Pi

Decision D12 keeps Docker off the measurement Pi unless it is shown not to perturb the numbers. The proposed equivalent is a `systemd-run` transient service, so no new package is installed:

| systemd property | Effect |
|---|---|
| `User=vtb-sandbox` (dedicated, no login, no sudo, no groups) | not the measurement user |
| `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_UNIX` | no network |
| `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`, `PrivateDevices=yes` | read-only system, no home, private `/tmp`, no device nodes |
| `ReadWritePaths=` only `/var/lib/vtb/canary` and `/var/lib/vtb/audit` | the only writable places |
| `NoNewPrivileges=yes`, `CapabilityBoundingSet=` (empty) | no privileges |
| `MemoryMax=256M`, `TasksMax=64` | bounded resources |
| `SystemCallFilter=@system-service` | drops rarely needed system calls |

**Unverified.** These are systemd's documented property names, but they have not been run on a Pi, and the systemd version there is unknown. The containment tests below decide whether the sandbox works; a property that does not exist or does not bite shows up as a failing test. `systemd-run` has no separate process-ID namespace by default, so on the Pi the sandbox user can see that other processes exist, though not their contents as another user. The alternative is `bubblewrap`, which does give namespaces at the cost of one more package.

Sandbox start-up is outside the timed region: `handle_ns` measures the handler only, so containment does not distort the Tier 1 latency result.

## 5. Containment tests (part of P2 acceptance)

A battery of inert escape attempts, run through the same entry point the vulnerable handler will use, on the laptop and again on the Pi. Each must fail or be confined:

1. Outbound connection to a loopback listener the harness opened: nothing arrives.
2. Writes outside the allowed directories (`/etc`, the working directory, the home directory): refused.
3. A write inside `/canary`: **succeeds**. This positive control matters, because an oracle that can never fire would make every defense look perfect.
4. A file the harness placed on the host outside every mount: not visible.
5. Capabilities: the effective set is empty.
6. Resource limits: a bounded burst of processes and a bounded allocation beyond the limits are refused or killed, and the test itself finishes quickly.
7. No persistence: after teardown and reset, `/canary` and `/audit` are empty.
8. The SQLite behaviour in E-012 holds in the sandbox: one statement per `execute()`, no extension loading.

The results are captured as evidence on each platform. The vulnerable handler is not written until the battery passes on the laptop; it does not run on the Pi until the battery passes there.

**Laptop status:** the battery is `tests/test_containment.py` (run on the host, where Docker is, with `VTB_REQUIRE_SANDBOX=1`). Its first run failed 3 of 14 tests and led to two clarifications of this design (the tmpfs ownership above, and the fresh-container-per-call runner) and a runner fix ([E-013](evidence/LOG.md)). It now passes 14 of 14 ([E-014](evidence/LOG.md)), so the condition for writing the vulnerable handler is met on the laptop. The Pi has not been run.

## 6. Residual risk

- A container-runtime or kernel escape. On macOS, Docker Desktop's VM adds a layer, but this is not a guarantee.
- The Pi sandbox has no process-ID namespace unless `bubblewrap` is chosen.
- A mistaken payload. Mitigated by the canary-only rule, review at G5, and the fact that the sandbox cannot touch the host.

## 7. Decisions (recorded 2026-09-24)

1. The laptop design in section 3 is approved.
2. The Pi sandbox is `systemd-run`, not `bubblewrap` (no new package on the measurement Pi).
3. The non-goals in section 2 and the residual risks in section 6 are accepted.
