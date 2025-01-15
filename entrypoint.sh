#!/bin/bash

function create_system_user_if_missing() {
  # This is needed in case of OpenShift-compatible container execution. In case of OpenShift random
  # User id is used when starting the image, however group 0 is kept as the user group. Our production
  # Image is OpenShift compatible, so all permissions on all folders are set so that 0 group can exercise
  # the same privileges as the default "runwhen" user, this code checks if the user is already
  # present in /etc/passwd and will create the system user dynamically
  if ! whoami &> /dev/null; then
    if [[ -w /etc/passwd ]]; then
      echo "${USER_NAME:-default}:x:$(id -u):0:${USER_NAME:-default} user:${RUNWHEN_HOME}:/sbin/nologin" \
          >> /etc/passwd
    fi
    export HOME="${RUNWHEN_HOME}"
  fi
}
## Handle permissions when UID is randomly assigned
create_system_user_if_missing


python3 generate_registry.py

mkdocs serve -f cc-registry/mkdocs.yml
