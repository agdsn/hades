.. _development:

===========
Development
===========

Docker Setup
============
Not everybody runs Debian on their systems.
Additionally one might not want to pollute their system with all the
dependencies and development tools, that are necessary to build and run Hades.
Docker provides an easy way to isolate the development environment from your
machine and to install the necessary requirements and tools.

Building & Running
------------------

Run the following command in the project root directory to build an image with
``docker-compose``:

.. code-block:: console

   docker-compose build --build-arg=UID=$(id -u) --build-arg=GID=$(id -g) hades

The ``UID`` and ``GID`` build args ensure, that the IDs of the user on your
machine match with the user and group created inside the container.

After you've successfully created the image, you can run the container:

.. code-block:: console

   docker-compose -up -d

This will start the container in background.
Inside the container ``systemd`` is started.
Running an init system like systemd in a container is not an usual setup, but
Hades integrates well with systemd and should be also be tested on systemd.

To enter the container run the following command:

.. code-block:: console

   docker-compose exec -u builder hades bash

Use in Production
-----------------
It probably doesn't make sense to run Hades inside Docker in production,
because the :ref:`networking` setup of Hades is much more involved than your
typical Docker application, which only needs to expose a few ports.
Hades requires Layer 2 connectivity, so you would need to pass interfaces into
the container or bridge the container interfaces on the host.
All of this is possible, the question is however if such a setup provides any
benefit.

Building the Documentation
==========================
The documentation for Hades is build with `sphinx <http://sphinx-doc.org>`.
An html build is stored in the gh-pages branch in order to host the
documentation using `GitHub Pages <https://pages.github.com/>`.

After cloning a repository for the first time, initialize the git submodules of
this repository:

.. code-block:: console

    git submodules update --init

To build the documentation, change into the ``docs`` directory and run:

.. code-block:: console

    make html

The documentation will built and stored in the ``docs/build/html`` directory.
This directory is actually a git submodule with a clone of the same repository,
but on a different branch, namely the special ``gh-pages`` branch.
This branch does not contain the project sources like ``master`` and is also
completely independent from the ``master`` branch.
Never merge or rebase these branch with each other!

You can view the documentation locally with your browser by opening the
``index.html`` file in the ``docs/build/html`` directory and if you are
satisfied, you can publish it on https://agdsn.github.io/hades/ by executing
the following commands in ``docs/build/html``:

.. code-block:: console

    git add .
    git commit
    git push origin gh-pages

.. warning::
   Don't mix up the root repository and its submodule in ``docs/build/html`` and
   be careful in which directory you are executing the git commands.

If you want you can then update the submodule relationship between root
repository and the gh-pages submodule by executing the following commands in
the **root** repository::

    git add docs/build/html
    git commit
