from pathlib import Path
from pint import UnitRegistry

definitions = Path("user/pint_def.txt")

ureg = UnitRegistry()
ureg.load_definitions(str(definitions.absolute()))
Q_ = ureg.Quantity