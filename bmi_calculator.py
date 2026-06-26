"""
BMI CALCULATOR - Python CLI

Calculates Body Mass Index (BMI) based on weight (kg) and height (m),
then classifies the result into WHO-standard health categories.
"""

import sys
import io

# Fix Unicode output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── ANSI Color Codes for styled terminal output ─────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
ORANGE = "\033[38;5;208m"
RED    = "\033[91m"
WHITE  = "\033[97m"
DIM    = "\033[2m"

# ─── BMI Categories (WHO Standard) ───────────────────────────────────────────
BMI_CATEGORIES = [
    (0,    18.5, "Underweight",        CYAN,   "⚠️  You may be underweight. Consider consulting a nutritionist."),
    (18.5, 25.0, "Normal weight",      GREEN,  "✅  Great! You have a healthy BMI. Keep maintaining your lifestyle."),
    (25.0, 30.0, "Overweight",         YELLOW, "⚠️  You are slightly overweight. A balanced diet and exercise may help."),
    (30.0, 35.0, "Obese (Class I)",    ORANGE, "🔶  Obesity Class I. Consider speaking with a healthcare professional."),
    (35.0, 40.0, "Obese (Class II)",   RED,    "🔴  Obesity Class II. Medical advice is strongly recommended."),
    (40.0, float("inf"), "Obese (Class III)", RED, "🚨  Obesity Class III. Please seek immediate medical guidance."),
]


def print_banner():
    """Print a styled ASCII banner."""
    print(f"\n{CYAN}{BOLD}")
    print("  +----------------------------------------------+")
    print("  |       ***   BMI  CALCULATOR   ***            |")
    print("  |      Body Mass Index -- WHO Standard         |")
    print("  +----------------------------------------------+")
    print(f"{RESET}")


def print_divider(char="-", width=50):
    print(f"{DIM}  {''.join([char] * width)}{RESET}")


def get_positive_float(prompt: str) -> float:
    """
    Repeatedly prompt the user until a valid positive float is entered.

    Args:
        prompt: The input prompt string.

    Returns:
        A positive float value entered by the user.
    """
    while True:
        try:
            value = float(input(prompt))
            if value <= 0:
                print(f"  {RED}✖  Value must be greater than zero. Please try again.{RESET}")
            else:
                return value
        except ValueError:
            print(f"  {RED}✖  Invalid input. Please enter a numeric value.{RESET}")


def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """
    Calculate BMI using the standard formula: BMI = weight / height².

    Args:
        weight_kg: Weight in kilograms.
        height_m:  Height in meters.

    Returns:
        Calculated BMI as a float.
    """
    return weight_kg / (height_m ** 2)


def classify_bmi(bmi: float) -> tuple:
    """
    Classify BMI into a WHO health category.

    Args:
        bmi: The calculated BMI value.

    Returns:
        A tuple of (category_name, color_code, advice_string).
    """
    for lower, upper, category, color, advice in BMI_CATEGORIES:
        if lower <= bmi < upper:
            return category, color, advice
    # Fallback (should never reach here)
    return "Unknown", WHITE, "Unable to classify BMI."


def display_bmi_chart():
    """Print a reference chart of all BMI categories."""
    print(f"\n  {BOLD}{WHITE}📊  BMI Reference Chart:{RESET}")
    print_divider()
    headers = f"  {'Category':<22} {'BMI Range':<18}"
    print(f"{DIM}{headers}{RESET}")
    print_divider()
    ranges = [
        (CYAN,   "Underweight",        "< 18.5"),
        (GREEN,  "Normal weight",      "18.5 – 24.9"),
        (YELLOW, "Overweight",         "25.0 – 29.9"),
        (ORANGE, "Obese (Class I)",    "30.0 – 34.9"),
        (RED,    "Obese (Class II)",   "35.0 – 39.9"),
        (RED,    "Obese (Class III)",  "≥ 40.0"),
    ]
    for color, cat, rng in ranges:
        print(f"  {color}{cat:<22}{RESET} {DIM}{rng}{RESET}")
    print_divider()


def run_calculator():
    """Main function: orchestrates user interaction and BMI calculation."""
    print_banner()

    print(f"  {WHITE}Enter your details below to calculate your BMI.{RESET}\n")

    # ── Collect Inputs ────────────────────────────────────────────────────────
    weight = get_positive_float(f"  {BOLD}⚖  Weight (kg) : {RESET}")
    height = get_positive_float(f"  {BOLD}📏  Height (m)  : {RESET}")

    # ── Calculate & Classify ──────────────────────────────────────────────────
    bmi = calculate_bmi(weight, height)
    category, color, advice = classify_bmi(bmi)

    # ── Display Results ───────────────────────────────────────────────────────
    print(f"\n  {BOLD}{WHITE}{'=' * 46}{RESET}")
    print(f"  {BOLD}{WHITE}       YOUR BMI RESULTS{RESET}")
    print(f"  {BOLD}{WHITE}{'=' * 46}{RESET}")
    print(f"\n  {DIM}Weight  :{RESET}  {WHITE}{weight:.1f} kg{RESET}")
    print(f"  {DIM}Height  :{RESET}  {WHITE}{height:.2f} m{RESET}")
    print(f"\n  {DIM}BMI     :{RESET}  {color}{BOLD}{bmi:.2f}{RESET}")
    print(f"  {DIM}Category:{RESET}  {color}{BOLD}{category}{RESET}")
    print(f"\n  {advice}{RESET}")
    print(f"\n  {BOLD}{WHITE}{'=' * 46}{RESET}\n")

    # ── Show Reference Chart ──────────────────────────────────────────────────
    display_bmi_chart()

    # ── Ask to Recalculate ────────────────────────────────────────────────────
    print()
    again = input(f"  {CYAN}Calculate again? (y/n): {RESET}").strip().lower()
    if again == "y":
        run_calculator()
    else:
        print(f"\n  {GREEN}Thank you for using the BMI Calculator. Stay healthy!{RESET}\n")


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_calculator()
