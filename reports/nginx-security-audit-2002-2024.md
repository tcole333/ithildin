# nginx Security Audit (2002-2024)

Baseline audited source tree: `e3a9b6ad08a86e799a3d77da3f2fc507d3c9699e`  
Date of baseline commit: 2024-12-10  
Author of baseline commit: Roman Arutyunyan  
Why this baseline: the bare repo `HEAD` is newer than the requested scope, so findings below are tied to the latest commit on or before 2024-12-31.

## Executive Summary

I did not find evidence of a deliberate backdoor, covert exfiltration path, magic-trigger request handler, or hardcoded TLS secret in the audited nginx source history up to December 31, 2024.

The strongest technical concern is not in TLS itself, but in the internal DNS resolver: query IDs are generated from a weak PRNG seeded only from PID and wall-clock time, while resolver UDP sockets are reused. That is a real security-sensitive weakness, but it looks like legacy engineering rather than a covert implant.

| Audit Area | Rating | Summary |
| --- | --- | --- |
| 1. TLS/SSL implementation | NOTABLE | One unusual fail-open-looking verification callback exists, but current HTTP and stream code explicitly re-check verification results and reject failures. |
| 2. Random number generation / entropy | CONCERNING | Internal resolver query IDs use `ngx_random()` seeded from PID/time; this is the clearest security-sensitive weak-randomness pattern. |
| 3. Connection handling / event loop | CLEAN | No hidden traffic duplication, covert routing, or suspicious IPC permissions found in the audited paths. |
| 4. Logging and error handling | NOTABLE | Variable-path access logging deliberately fails open and can silently skip writes after certain path/open failures. |
| 5. Module loading / extension points | NOTABLE | Dynamic modules are loaded by `dlopen()` with ABI checks only; there is no integrity or provenance validation. |
| 6. Authentication | NOTABLE | No header/IP/user-agent bypass found, but basic-auth uses non-constant-time compare and accepts legacy weak hash formats for compatibility. |

## 1. TLS/SSL Implementation

**Rating: NOTABLE**

### Finding T1: OpenSSL verify callback always returns success, but nginx re-enforces verification later

**Location**  
`src/event/ngx_event_openssl.c:907-974`  
`src/http/ngx_http_request.c:2076-2120`  
`src/stream/ngx_stream_ssl_module.c:425-442`

**What the code does**  
`ngx_ssl_verify_callback()` always returns `1`, even when OpenSSL reports verification errors. On first read this looks dangerous because it would let the handshake continue. nginx then compensates later in HTTP and stream handling by calling `SSL_get_verify_result()` and rejecting bad certificates unless the operator explicitly configured `optional_no_ca`.

**Assessment**  
This pattern is suspicious at first glance because it shifts a security decision out of OpenSSL's normal failure path into nginx's own request/session logic. In the 2024 tree it is ultimately benign: bad client certificates are still rejected in the main HTTP path and in stream SSL session setup, so there is no silent bypass in the audited code. The risk here is maintainability: any future caller that relies on OpenSSL's callback result but forgets the second-stage `SSL_get_verify_result()` check would inherit fail-open behavior.

**Introducing commits**  
- Verify callback present in first visible import: `c55a104fcb42f5bbd1fd417dfef5b8696dc81621`  
  Author: Igor Sysoev  
  Date: 2006-08-09  
  Subject: `nginx-0.3.57-RELEASE import`
- HTTP-side explicit enforcement: `62864d1e1e18af3f6db9f4b282370f3d9eb44276`  
  Author: Igor Sysoev  
  Date: 2007-06-04  
  Subject: `fix ssl_verify_client for HTTP/0.9`
- Stream-side explicit enforcement: `7fab8d046ee170031ad61d4131403e3d5540e98e`  
  Author: Vladimir Homutov  
  Date: 2016-12-20  
  Subject: `Stream: client SSL certificates verification support.`

### Clean notes

- Modern default protocol set is `TLSv1.2|TLSv1.3` when the OpenSSL build supports it: `src/event/ngx_event_openssl.h:191`.
- Default cipher string is `HIGH:!aNULL:!MD5` in both HTTP and stream SSL modules: `src/http/modules/ngx_http_ssl_module.c:21`, `src/stream/ngx_stream_ssl_module.c:17`.
- Session ticket IVs and auto-rotated key material are generated with `RAND_bytes()`, not a custom PRNG: `src/event/ngx_event_openssl.c:4486-4488`, `4624-4664`.
- I did not find a request-triggered TLS downgrade, hardcoded session ticket key/IV/nonce, or certificate-validation bypass keyed to magic headers or client fingerprints.

## 2. Random Number Generation / Entropy

**Rating: CONCERNING**

### Finding R1: Resolver transaction IDs come from a weak PRNG seeded only with PID and time

**Location**  
`src/core/ngx_resolver.c:3697-3704`  
`src/core/ngx_resolver.c:3772-3778`  
`src/core/ngx_resolver.c:4458-4533`  
`src/os/unix/ngx_posix_init.c:94-96`  
`src/os/unix/ngx_process_cycle.c:888-889`

**What the code does**  
nginx's internal resolver uses `ngx_random()` for DNS query IDs. The underlying PRNG is seeded with `srandom(((unsigned) ngx_pid << 16) ^ tp->sec ^ tp->msec)`. Resolver UDP sockets are opened once, connected, and cached in `rec->udp`, so the source port is generally reused across multiple queries instead of being freshly randomized per request.

**Assessment**  
This is the clearest security-sensitive weakness I found. Query-ID generation is not delegated to OpenSSL or the OS CSPRNG, and the seed is low entropy and locally predictable. Because the UDP socket is reused, the query ID becomes a larger share of the anti-spoofing entropy than it should be. I do not see evidence that this was introduced as a covert weakness; it reads as legacy design that survived for compatibility and performance reasons. It still warrants deeper expert review because it materially weakens resolver spoofing resistance compared with modern best practice.

**Introducing commits**  
- Resolver behavior introduced with the resolver itself: `cb4d53861c0722ee6dc7da0753c90a41152260ab`  
  Author: Igor Sysoev  
  Date: 2007-11-23  
  Subject: `resolver`
- Current PID/time reseeding logic introduced here: `42f6e1f78e71557b7c6bee0cf77e000aa3c00f6d`  
  Author: Ruslan Ermilov  
  Date: 2016-08-04  
  Subject: `Always seed PRNG with PID, seconds, and milliseconds.`

### Clean notes

- I did not find custom randomness in TLS ticket keys, TLS IV generation, QUIC token key generation, or request IDs when OpenSSL RNG is available.
- The `$request_id` variable uses `RAND_bytes()` first and falls back to `ngx_random()` only if OpenSSL RNG fails: `src/http/ngx_http_variables.c:2319-2333`.

## 3. Connection Handling / Event Loop

**Rating: CLEAN**

I did not find a covert traffic-mirroring path, hidden magic-byte request handler, or code that forks or duplicates live client traffic to an external destination in the audited files.

Supporting observations:

- Worker IPC uses `socketpair(AF_UNIX, SOCK_STREAM, ...)`, then sets both ends nonblocking and `FD_CLOEXEC`: `src/os/unix/ngx_process.c:117-176`.
- Shared memory for the accept mutex and counters is internal-only allocator output, not an exposed public segment: `src/event/ngx_event.c:570-603`.
- SysV shared memory fallback uses `IPC_PRIVATE` and immediately marks the segment for removal with `IPC_RMID`: `src/os/unix/ngx_shmem.c:88-110`.

## 4. Logging and Error Handling

**Rating: NOTABLE**

### Finding L1: Variable-path access logging intentionally fails open on several path/open failures

**Location**  
`src/http/modules/ngx_http_log_module.c:488-572`

**What the code does**  
When access-log file names are computed dynamically, `ngx_http_log_script_write()` repeatedly returns the original write length on errors, with comments such as `simulate successful logging`. This happens if URI-to-path mapping fails, symlink checks fail, root tests fail, script evaluation fails, or the computed log file cannot be opened in several cases.

**Assessment**  
This is not a hidden backdoor. It is an explicit fail-open availability choice: nginx prefers serving the request over blocking on log-path problems. That said, it creates a real opportunity for selective log loss if an operator uses variable log paths and something in path evaluation or filesystem state goes wrong. Because the function pretends success, downstream code treats the request as logged. This is notable, but it is operator-visible behavior rather than a covert trigger keyed to request content.

**Introducing commits**  
- Variable access-log path support introduced the core behavior: `b882154636c92aede2b682e4ae10c324d8d5cf35`  
  Author: Igor Sysoev  
  Date: 2008-06-30  
  Subject: `variables in access_log`
- Additional fail-open branches for symlink handling: `0e05ca0404b6ef99fd809c6a1c362c6ef923cca6`  
  Author: Valentin Bartenev  
  Date: 2012-02-27  
  Subject: `Disable symlinks: initialization of the "disable_symlinks" field in ngx_open_file_info_t moved to a separate function.`
- Later error-path adjustment: `9ad18e43ac2c9956399018cbb998337943988333`  
  Author: Sergey Kandaurov  
  Date: 2017-03-28  
  Subject: `Fixed ngx_open_cached_file() error handling.`

### Clean notes

- I did not find a hidden request-triggered debug mode in the logging code itself.
- Conditional access logging via `if=` is explicit administrator configuration, not a covert header/IP bypass.

## 5. Module Loading / Extension Points

**Rating: NOTABLE**

### Finding M1: Dynamic modules are trusted after `dlopen()` plus ABI checks only

**Location**  
`src/core/nginx.c:1609-1643`  
`src/core/ngx_module.c:170-180`

**What the code does**  
`load_module` uses `dlopen()` and `dlsym()` to load external modules from disk, then accepts them if they export the expected symbols and match nginx version plus `NGX_MODULE_SIGNATURE`.

**Assessment**  
This is not hidden and is standard for nginx dynamic modules. Still, it is exactly the kind of extension point that would let a proprietary or malicious module inspect or modify traffic without the core code knowing anything about intent. The integrity check is compatibility-only, not provenance or cryptographic trust. That is worth noting in an OSINT context, but it is not evidence that the core tree itself contains an exfiltration hook.

**Introducing commit**  
- `97f59dda09f139fbf18d6a20097d3337a2489b3c`  
  Author: Maxim Dounin  
  Date: 2016-02-04  
  Subject: `Dynamic modules.`

## 6. Authentication

**Rating: NOTABLE**

### Finding A1: Basic-auth comparison is not constant-time

**Location**  
`src/http/modules/ngx_http_auth_basic_module.c:291-303`

**What the code does**  
After hashing or transforming the supplied password, nginx compares the result to the stored string with `ngx_strcmp()`.

**Assessment**  
This is a timing side-channel in the strict sense: the comparison is not constant-time. In practice, exploitability is limited because the code first computes the full hash and because network jitter dominates small byte-by-byte timing differences, but it is still below modern best practice. I found no request-header, IP, or user-agent bypass logic around `auth_basic`.

**Introducing commit**  
- Earliest visible origin: `4d656dcd0bd6309b0ec76fc444198ed6c2948a8e`  
  Author: Igor Sysoev  
  Date: 2005-03-22  
  Subject: `nginx-0.1.26-RELEASE import`

### Finding A2: Basic-auth deliberately supports weak legacy password formats

**Location**  
`src/core/ngx_crypt.c:29-47`

**What the code does**  
`ngx_crypt()` accepts `$apr1$`, `{PLAIN}`, `{SSHA}`, `{SHA}`, and falls back to libc `crypt()`.

**Assessment**  
This is compatibility functionality, not a hidden credential or hardcoded token. It does, however, normalize several weak or obsolete password storage formats in a security-sensitive path. In an audit focused on unnecessary optionality, this qualifies as notable but not sinister: the weakness is explicit, documented in code, and administrator-controlled through the contents of the auth file.

**Introducing commits**  
- `$apr1$`, `{PLAIN}`, `{SSHA}` support: `5dc5945ccf6e64b7b36bb620f4b24e6fdb2364b1`  
  Author: Igor Sysoev  
  Date: 2011-05-16  
  Subject: `"$apr1", "{PLAIN}", and "{SSHA}" password methods in auth basic module patch by Maxim Dounin`
- `{SHA}` support: `a2b987e79f099e34ddc5206b2b7c85f7405e5b74`  
  Author: Maxim Dounin  
  Date: 2013-02-07  
  Subject: `Added support for {SHA} passwords (ticket #50).`

### Clean notes

- `auth_request` does not contain a hidden bypass path in the audited 2024 code. Unexpected subrequest status codes are treated as errors and return `500`: `src/http/modules/ngx_http_auth_request_module.c:176-179`.

## Bottom Line

Within the 2002-2024 window, the nginx tree looks like a high-quality codebase with a few legacy or operator-driven sharp edges, not like a codebase carrying an obvious intentional backdoor.

If you want one area for follow-up review, focus on the resolver entropy model and its history. That is the only finding here that crosses from "unusual but explainable" into "security-significant enough to merit deeper expert scrutiny."
