Hades
=====
Hades is the AG DSN authentication and authorization system

Documentation for Hades can be found on [here](https://agdsn.github.io/hades/)


Building
========
Enter the `hades` docker container:
```shell
docker compose exec --user=builder --workdir=/build/hades hades bash
````

<details><summary>Building arpreq</summary>

```shell
(
   cd vendor \
   && (cd arpreq && dpkg-buildpackage --no-sign -b) \
   && sudo dpkg -i python3-arpreq_*.deb;
)
```
</details>

<details><summary>Building hades</summary>

```shell
dpkg-buildpackage --no-sign -b \
&& sudo dpkg -i ../hades_*.deb \
&& sudo systemctl start hades
```
</details>

Troubleshooting
===============
<details><summary>Issues with the db schema / access</summary>
Try recreating the costgresql-cluster in the container:

```shell
sudo systemctl stop hades-database
sudo /usr/lib/hades/control-database.sh clear
sudo systemctl start hades-database
```
</details>

<details><summary><code>setup.py</code> cannot be deleted when rebuilding</summary>
This can happen when the template instantiation command fails,
which causes <code>setup.py</code> to not be emitted.
Thus, <code>setup.py clean</code> cannot possibly work.
The quickfix is to

```shell
touch /build/hades/setup.py
```
and then rebuild.
</details>

Misc
====
<details><summary>Drawing a systemd unit dependency graph</summary>

Inside the docker container:
```shell
sydstemd-analyze dot --to-pattern='hades*' > hades.dot
```

Then on your system (assuming it has `dot` installed):
```shell
dot -Tsvg <(<hades.dot | grep -v 'target') > hades.svg
xdg-open hades.svg
```
</details>
