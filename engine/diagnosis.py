def generate_diagnosis(results):
    """Apply transparent rules to measured results."""

    evidence = []
    actions = []
    issues = []

    # Extract test results
    reachability = results["reachability"]
    ping = results["ping"]
    dns = results["dns"]
    https = results["https"]
    throughput = results.get("throughput", {})

    loss = ping.get("packet_loss_pct")
    latency = ping.get("latency_ms")
    jitter = ping.get("jitter_ms")
    download = throughput.get("download_mbps")
    upload = throughput.get("upload_mbps")

    # 1. Check internet reachability
    if not reachability.get("reachable"):
        issues.append("IP_REACHABILITY")

        evidence.append(
            "A TCP connection to the selected public IP address failed."
        )

        actions.append(
            "Check Wi-Fi/Ethernet connection, router status, "
            "and firewall settings."
        )

    # 2. Check packet loss
    if loss is not None and loss > 2:
        issues.append("PACKET_LOSS")

        evidence.append(
            f"Measured packet loss was {loss}%, "
            "above the prototype warning threshold of 2%."
        )

        actions.append(
            "Repeat the test and compare results using another destination."
        )

    # 3. Check latency
    if latency is not None and latency > 150:
        issues.append("HIGH_LATENCY")

        evidence.append(
            f"Average ping latency was {latency} ms, "
            "above the prototype warning threshold of 150 ms."
        )

        actions.append(
            "Check local Wi-Fi signal quality and repeat the test."
        )

    # 4. Check jitter
    if jitter is not None and jitter > 30:
        issues.append("HIGH_JITTER")

        evidence.append(
            f"Jitter was {jitter} ms, "
            "above the prototype threshold of 30 ms."
        )

        actions.append(
            "Check Wi-Fi stability, network interference "
            "and background traffic. Repeat the measurement."
        )

    # 5. Check throughput (skipped if the speed test was off or failed)
    if download is not None and download < 5:
        issues.append("SLOW_DOWNLOAD")

        evidence.append(
            f"Measured download speed was {download} Mbps, "
            "below the prototype warning threshold of 5 Mbps."
        )

        actions.append(
            "Pause other downloads or streaming, test closer to the router, "
            "and repeat. If it stays low, compare with your ISP plan speed."
        )

    if upload is not None and upload < 1:
        issues.append("SLOW_UPLOAD")

        evidence.append(
            f"Measured upload speed was {upload} Mbps, "
            "below the prototype warning threshold of 1 Mbps."
        )

        actions.append(
            "Check for background uploads such as cloud backups, "
            "then repeat the test."
        )

    # 6. Check DNS
    if not dns.get("resolved") and reachability.get("reachable"):
        issues.append("POSSIBLE_DNS")

        evidence.append(
            "Direct IP connectivity succeeded, "
            "but domain-name resolution failed."
        )

        actions.append(
            "Check the configured DNS resolver or try another trusted DNS resolver."
        )

    # 7. Check HTTPS
    if not https.get("connected") and reachability.get("reachable"):
        issues.append("HTTPS_CONNECTION")

        evidence.append(
            "Direct IP connectivity succeeded, "
            "but the HTTPS hostname connection failed."
        )

        actions.append(
            "Check hostname resolution, firewall/proxy settings, and retry."
        )

    # 8. Generate final diagnosis
    if not issues:

        title = "No major issue detected by the current checks"
        level = "NORMAL"

        explanation = (
            "The selected IP reachability, ping, DNS, HTTPS and speed checks "
            "did not show a major problem. This does not guarantee "
            "that every application or network route is healthy."
        )

        evidence.append(
            "All completed checks were within the prototype's basic pass conditions."
        )

        actions.append(
            "If problems continue, repeat tests while the issue is happening "
            "and compare another destination."
        )

    elif issues == ["POSSIBLE_DNS"]:

        title = "Possible DNS resolution problem"
        level = "WARNING"

        explanation = (
            "The selected IP endpoint was reachable, but the test domain "
            "could not be resolved. This pattern is consistent with a DNS issue."
        )

    elif set(issues) <= {"SLOW_DOWNLOAD", "SLOW_UPLOAD"}:

        title = "Slow internet speed detected"
        level = "WARNING"

        explanation = (
            "Connectivity tests passed, but the measured throughput was low. "
            "This may come from Wi-Fi quality, network congestion, or your "
            "ISP plan, and these checks cannot tell which."
        )

    else:

        title = "Potential connectivity issue detected"
        level = "WARNING"

        explanation = (
            "One or more network tests produced abnormal results. "
            "The evidence identifies potential problem areas but does not "
            "prove the exact faulty device or service."
        )

    # 9. Return diagnosis
    return {
        "title": title,
        "level": level,
        "evidence": evidence,
        "explanation": explanation,
        "actions": actions,
        "issue_codes": issues
    }