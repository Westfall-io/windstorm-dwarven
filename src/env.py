# Copyright (c) 2023-2024 Westfall Inc.
#
# This file is part of Windstorm-Dwarven.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, and can be found in the file NOTICE inside this
# git repository.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

SQLHOST = os.environ.get("SQLHOST","localhost:5432")
HARBORPATH = os.environ.get("HARBORPATH","core.harbor.domain/")

PGUSER = os.environ.get("PGUSER","postgres")
PGPASSWD = os.environ.get("PGPASSWD","mysecretpassword")
PGDBNAME = os.environ.get("PGDBNAME","pgdb")

KCREALM = os.environ.get("KCREALM","test")
KCADDR = os.environ.get("KCADDR","https://keycloak.digitalforge.app")
