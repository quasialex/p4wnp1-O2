#!/bin/bash

PAYLOAD=$(cat /opt/p4wnp1/config/active_payload)
bash /opt/p4wnp1/payloads/$PAYLOAD
