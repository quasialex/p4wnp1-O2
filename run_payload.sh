#!/bin/bash
# Wrapper for backward compatibility - launches run.sh which handles
# gadget setup and payload execution based on the active payload file.
P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
exec "$P4WN_HOME/run.sh"
