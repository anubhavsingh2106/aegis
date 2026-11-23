
import argparse
import json
from pathlib import Path

from aegis.ai.context import build_context_package
from aegis.ai.outbound import (
    create_outbound_approval,
    inspect_outbound_context,
)
from aegis.graph.impact import analyze_impact
from aegis.verification.docker_runner import compare_revisions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aegis — Predictive Software Reliability Engine"
    )
    parser.add_argument("repo", help="Path to a Git repository")
    parser.add_argument("--base", required=True, help="Base Git revision")
    parser.add_argument(
        "--output",
        default="aegis-report.json",
        help="Path for the JSON report",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run baseline-versus-head verification",
    )
    parser.add_argument(
        "--verify-mode",
        choices=("docker", "native", "analysis-only"),
        default=None,
        help="Verification backend (default: docker when verification is requested)",
    )
    parser.add_argument(
        "--trust-repo",
        action="store_true",
        help="Explicitly trust this repository for native code execution",
    )
    parser.add_argument(
        "--inspect-context",
        action="store_true",
        help="Build a redacted AI context package and outbound preview without sending data",
    )
    parser.add_argument(
        "--approve-context",
        action="store_true",
        help="Request explicit approval for the inspected context payload",
    )
    parser.add_argument(
        "--approval-output",
        default="aegis-approval.json",
        help="Path for the local approval record",
    )

    args = parser.parse_args()

    verify_requested = args.verify or args.verify_mode is not None
    mode = args.verify_mode or "docker"

    if args.trust_repo and mode != "native":
        parser.error("--trust-repo can only be used with --verify-mode native")

    if mode == "native" and not args.trust_repo:
        parser.error(
            "Native execution runs code without a security sandbox. "
            "Only use it for trusted repositories; pass --trust-repo "
            "to explicitly accept this risk."
        )

    if args.approve_context and not args.inspect_context:
        parser.error("--approve-context requires --inspect-context")

    if (
        args.approve_context
        and Path(args.output).resolve() == Path(args.approval_output).resolve()
    ):
        parser.error("Report and approval output paths must be different")

    try:
        report = analyze_impact(args.repo, args.base)

        if args.inspect_context:
            context_package = build_context_package(report)
            report["context_package"] = context_package

            preview = inspect_outbound_context(context_package)
            report["outbound_preview"] = preview

            if args.approve_context:
                print("\n========== OUTBOUND PAYLOAD ==========")
                print(json.dumps(preview["payload"], indent=2))
                print("=======================================")
                print(f"SHA-256: {preview['payload_sha256']}")
                print("\nReview the complete payload above.")

                confirmation = input(
                    'Type APPROVE to approve this exact payload: '
                )

                if confirmation == "APPROVE":
                    approval = create_outbound_approval(
                        preview,
                        user_confirmed=True,
                    )

                    approval_path = Path(args.approval_output).resolve()
                    approval_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    approval_path.write_text(
                        json.dumps(approval, indent=2),
                        encoding="utf-8",
                    )

                    print(f"Approval record written to: {approval_path}")
                else:
                    print("Approval not granted. No approval record created.")

        if verify_requested:
            if mode == "analysis-only":
                report["verification"] = {
                    "status": "verification_skipped",
                    "regression_detected": False,
                    "execution_mode": mode,
                    "reason": "Analysis-only mode; no tests were executed.",
                }
            else:
                native_runner = None

                if mode == "native":
                    try:
                        from aegis.verification.native_runner import NativeRunner
                    except ImportError as exc:
                        raise RuntimeError(
                            "Native runner is not available. "
                            "Ensure native_runner.py and its dependencies "
                            "are installed correctly."
                        ) from exc

                    native_runner = NativeRunner()

                report["verification"] = compare_revisions(
                    args.repo,
                    args.base,
                    mode=mode,
                    trusted_repository=args.trust_repo,
                    native_runner=native_runner,
                )

        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print(f"Changed functions: {len(report['changed_functions'])}")
        print(
            "Potentially affected callers: "
            f"{len(report['potentially_affected_callers'])}"
        )

        if args.inspect_context:
            preview = report["outbound_preview"]
            print(
                "Context snippets: "
                f"{len(preview['payload']['snippets'])}"
            )
            print("Network requests: 0")

            if not args.approve_context:
                print("Outbound approval required: true")

        if verify_requested:
            print(
                "Verification status: "
                f"{report['verification']['status']}"
            )

        print(f"Report written to: {output}")

    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Aegis failed: {exc}\n")


if __name__ == "__main__":
    main()
