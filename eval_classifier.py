"""
Standalone evaluation script for the rule-based intent classifier.
Not part of the test suite -- run manually to produce real accuracy/latency
numbers for documentation purposes.
"""
import time
import statistics
from app.services.classifier import classify_intent

# Labeled eval set: natural phrasings a real user might type, not copied
# from the unit tests. Meant to approximate real-world variety per intent.
EVAL_SET = [
    ("I can't log into my account, it keeps saying wrong password", "login_issue"),
    ("Forgot my password and the reset email never arrived", "login_issue"),
    ("My account got locked after too many attempts", "login_issue"),
    ("two factor authentication isn't sending me a code", "login_issue"),
    ("Getting invalid credentials error even though I'm sure it's right", "login_issue"),
    ("I was charged twice for the same subscription", "payment_issue"),
    ("My card was declined but funds were still taken", "payment_issue"),
    ("Need a copy of my invoice from last month", "payment_issue"),
    ("Why is the pricing plan different from what I signed up for", "payment_issue"),
    ("Refund request for a duplicate transaction", "payment_issue"),
    ("Please delete my account and all my data", "account_issue"),
    ("I want to cancel my subscription and close my account", "account_issue"),
    ("Need to update my email address on file", "account_issue"),
    ("How do I change my profile name and phone number", "account_issue"),
    ("Please deactivate my account under GDPR", "account_issue"),
    ("The app keeps crashing every time I open it", "technical_issue"),
    ("Getting a weird error message on checkout", "technical_issue"),
    ("The dashboard is extremely slow to load lately", "technical_issue"),
    ("App freezes and times out on the upload page", "technical_issue"),
    ("This feature is completely broken and not working", "technical_issue"),
    ("Could you add a dark mode option please", "feature_request"),
    ("It would be great to implement bulk export", "feature_request"),
    ("Please improve the search so results are more relevant", "feature_request"),
    ("Wish there was a way to schedule posts in advance", "feature_request"),
    ("Can you build an integration with Slack", "feature_request"),
    ("How do I use the export feature, any guide?", "general_query"),
    ("What are the steps to set up two factor auth", "general_query"),
    ("How much does the pro plan cost", "general_query"),
    ("What's included if I upgrade my plan", "general_query"),
    ("Just wondering how this product works in general", "general_query"),
    ("asdkj random gibberish text 12345", "unknown"),
    ("", "unknown"),
]


def main():
    correct = 0
    latencies = []
    misclassified = []

    for text, expected in EVAL_SET:
        start = time.perf_counter()
        result = classify_intent(text)
        latencies.append((time.perf_counter() - start) * 1000)  # ms

        predicted = result["intent"]
        if predicted == expected:
            correct += 1
        else:
            misclassified.append((text, expected, predicted))

    total = len(EVAL_SET)
    accuracy = correct / total * 100
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]

    print(f"Eval set size: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.1f}%")
    print(f"Latency p50: {p50:.3f} ms")
    print(f"Latency p95: {p95:.3f} ms")
    print(f"Latency mean: {statistics.mean(latencies):.3f} ms")

    if misclassified:
        print("\nMisclassified:")
        for text, expected, predicted in misclassified:
            print(f"  '{text}' -> expected={expected}, got={predicted}")


if __name__ == "__main__":
    main()
