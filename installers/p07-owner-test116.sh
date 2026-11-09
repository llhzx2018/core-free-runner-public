#!/usr/bin/env bash
# RETIRED: this test installer incorrectly tried to clone a private product
# repository and install git on the Owner's CloudPanel VPS.
# P07 candidate must instead be prebuilt off-server, signed/hashed, and
# delivered over an authorized package endpoint before manual trial.
set -Eeuo pipefail
printf '%s\n' \
  'P07_TEST116_BOOTSTRAP_RETIRED=YES' \
  'REASON=SERVER_SIDE_GIT_AND_PRIVATE_SOURCE_CLONE_NOT_ALLOWED' \
  'REQUIRED=PREBUILT_SHA256_PINNED_CANDIDATE_PACKAGE' \
  'OLD_RELEASE115_UNCHANGED=YES' \
  'NO_SYSTEM_PACKAGE_INSTALL=YES' \
  'NO_DATABASE_OR_DNS_CHANGES=YES'
exit 13
