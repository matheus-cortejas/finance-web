#!/usr/bin/env python3
import os
import sys

# ensure src is on path so we can import the package
ROOT = os.path.dirname(__file__)
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from monitoring.monitor import main

if __name__ == '__main__':
    main()
