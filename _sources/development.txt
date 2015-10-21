===========
Development
===========

Building the Documentation
==========================
The documentation for Hades is build with `sphinx <http://sphinx-doc.org>`.
An html build is stored in the gh-pages branch in order to host the
documentation using `GitHub Pages <https://pages.github.com/>`.

After cloning a repository for the first time, initialize the git submodules of
this repository::

    git submodules update --init

To build the documentation, change into the ``docs`` directory and run::

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
the following commands in ``docs/build/html``::

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
