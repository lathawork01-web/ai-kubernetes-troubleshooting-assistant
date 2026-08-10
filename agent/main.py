"""
main.py — CLI entrypoint.

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    python main.py --pod payment-api-7d9f8c --namespace production \\
        --question "Why is this pod crashing?"
"""

import argparse
from graph import investigate


def main():
    parser = argparse.ArgumentParser(description="AI Kubernetes Troubleshooting Assistant")
    parser.add_argument("--pod", required=True, help="Name of the pod to investigate")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--question", default="Why is this pod having issues?")
    args = parser.parse_args()

    print(f"Investigating {args.namespace}/{args.pod}...\n")
    result = investigate(args.question, args.pod, args.namespace)
    print(result)


if __name__ == "__main__":
    main()
