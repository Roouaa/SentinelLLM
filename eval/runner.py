import sys
import yaml

ATTACKS_PATH = "eval/cases/attacks.yaml"

try:
    with open(ATTACKS_PATH) as stream:
        attacks = yaml.safe_load(stream)
except FileNotFoundError:
    print(f"Cannot find the attacks file at {ATTACKS_PATH}")
    sys.exit(1)
except yaml.YAMLError as exc:
    print(f"The attacks file at {ATTACKS_PATH} is not valid YAML:\n{exc}")
    sys.exit(1)

print(attacks)
