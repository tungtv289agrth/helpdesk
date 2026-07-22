#!/bin/bash

HOST=10.28.0.36
USER=tungtv289
DEST=/home/dministrator/code/helpdesk

rsync -av \
  --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.gitignore' \
  --rsync-path="sudo rsync" \
  ./ \
  ${USER}@${HOST}:${DEST}

ssh ${USER}@${HOST} \
  "sudo chown -R dministrator:dministrator ${DEST}"
