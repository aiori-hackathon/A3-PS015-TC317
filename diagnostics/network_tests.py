import platform
import re
import socket
import subprocess
import time



def ping_host(host="1.1.1.1", count=5, timeout_ms=1200):
    

    system = platform.system().lower()

    if system == "windows":
        command = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
    else:
        command = [
            "ping", "-c", str(count),
            "-W", str(max(1, round(timeout_ms / 1000))), host
        ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=(count * 2) + 5
        )

        output = (completed.stdout or "") + (completed.stderr or "")

    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "details": f"Ping test failed: {exc}",
            "latency_ms": None,
            "packet_loss_pct": None,
            "jitter_ms": None
        }

    # Extract individual ping response times.
    matches = re.findall(
        r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
        output,
        re.IGNORECASE
    )

    # Windows may report time<1ms.
    samples = [float(value) for value in matches]

    less_than_one = len(re.findall(r"time<1ms", output, re.IGNORECASE))
    samples.extend([0.5] * less_than_one)

    # Extract packet loss.
    loss_match = re.search(
        r"(\d+(?:\.\d+)?)%\s*(?:packet\s*)?loss",
        output,
        re.IGNORECASE
    )

    if loss_match:
        packet_loss = float(loss_match.group(1))
    else:
        return {
            "status": "UNKNOWN",
            "details": "Could not interpret ping output.",
            "latency_ms": None,
            "packet_loss_pct": None,
            "jitter_ms": None
        }

    # Calculate average latency.
    latency = (
        sum(samples) / len(samples)
        if samples else None
    )

    # Calculate average absolute variation between successive RTTs.
    if len(samples) >= 2:
        differences = [
            abs(samples[i] - samples[i - 1])
            for i in range(1, len(samples))
        ]
        jitter = sum(differences) / len(differences)
    else:
        jitter = None

    if latency is None:
        status = "WARNING"
    elif packet_loss > 2 or latency > 150:
        status = "WARNING"
    elif jitter is not None and jitter > 30:
        status = "WARNING"
    else:
        status = "GOOD"

    details = (
        f"Average latency: {latency:.1f} ms; "
        f"packet loss: {packet_loss}%; "
        f"jitter: {jitter:.1f} ms"
        if latency is not None and jitter is not None
        else f"Latency: {latency}; packet loss: {packet_loss}%; "
             f"jitter: {jitter}"
    )

    return {
        "status": status,
        "details": details,
        "latency_ms": round(latency, 2) if latency is not None else None,
        "packet_loss_pct": packet_loss,
        "jitter_ms": round(jitter, 2) if jitter is not None else None
    }



def check_dns(domain="example.com"):
    """Resolve a domain and measure DNS lookup duration."""
    started = time.perf_counter()
    try:
        addresses = socket.getaddrinfo(domain, None)
        elapsed_ms = (time.perf_counter() - started) * 1000
        ip_address = addresses[0][4][0] if addresses else "Address not returned"
        return {
            "status": "GOOD",
            "details": f"{domain} resolved to {ip_address} in {elapsed_ms:.1f} ms",
            "duration_ms": round(elapsed_ms, 1),
            "resolved": True,
        }
    except socket.gaierror as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "status": "WARNING",
            "details": f"DNS resolution failed for {domain}: {exc}",
            "duration_ms": round(elapsed_ms, 1),
            "resolved": False,
        }


def check_https(host="example.com", port=443, timeout=4):
    """Check whether a TCP connection to an HTTPS endpoint can be established."""
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "status": "GOOD",
            "details": f"TCP connection to {host}:{port} succeeded in {elapsed_ms:.1f} ms",
            "connected": True,
        }
    except OSError as exc:
        return {
            "status": "WARNING",
            "details": f"Could not connect to {host}:{port}: {exc}",
            "connected": False,
        }


def check_ip_reachability(host="1.1.1.1", port=443, timeout=4):
    """Check direct IP reachability using a TCP connection."""
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "status": "GOOD",
            "details": f"Direct IP connection to {host}:{port} succeeded in {elapsed_ms:.1f} ms",
            "reachable": True,
        }
    except OSError as exc:
        return {
            "status": "WARNING",
            "details": f"Direct IP connection to {host}:{port} failed: {exc}",
            "reachable": False,
        }


def measure_throughput():
    """
    Measure internet download and upload speed.
    """

    try:
        import speedtest

        # Create speed test object
        tester = speedtest.Speedtest(timeout=15)

        # Select the best available server
        server = tester.get_best_server()

        # Measure download speed
        download_bps = tester.download()

        # Measure upload speed
        upload_bps = tester.upload()

        # Convert to Mbps
        download_mbps = download_bps / 1_000_000
        upload_mbps = upload_bps / 1_000_000

        return {
            "status": "MEASURED",
            "download_mbps": round(download_mbps, 2),
            "upload_mbps": round(upload_mbps, 2),
            "server": server.get("name", "Unknown"),
            "details": (
                f"Download: {download_mbps:.2f} Mbps; "
                f"Upload: {upload_mbps:.2f} Mbps"
            )
        }

    except Exception as exc:

        return {
            "status": "UNKNOWN",
            "download_mbps": None,
            "upload_mbps": None,
            "server": None,
            "details": f"Speed test failed: {exc}"
        }


def run_all_tests():

    reachability = check_ip_reachability()
    ping = ping_host()
    dns = check_dns()
    https = check_https()

    # New throughput measurement
    throughput = measure_throughput()

    return {
        "reachability": reachability,
        "ping": ping,
        "dns": dns,
        "https": https,
        "throughput": throughput
    }

