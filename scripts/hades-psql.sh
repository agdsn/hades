#!/bin/bash

sudo -u hades-database psql -h /run/hades/database hades "$@"
