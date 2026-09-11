"""Small preflight guard; actual REAPER GUI compilation remains a release gate."""
import re

def validate_literals(source):
    # Ignore comments and strings; numeric E notation in EEL code caused M8's GUI failure.
    code = re.sub(r'"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\n]*', ' ', source)
    match = re.search(r'(?<![\w.])(?:\d+(?:\.\d*)?|\.\d+)[eE][+-]?\d+', code)
    if match:
        raise ValueError('Use decimal literals in JSFX EEL code: '+match.group())
