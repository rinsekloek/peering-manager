# Upgrading

As with the initial installation, you can upgrade Peering Manager by pulling
the latest changes from the Git repository.

Assuming that Peering Manager is installed at `/opt/peering-manager`. Pull down
the most recent changes of the master branch with:
```
# cd /opt/peering-manager
# git pull
```

## Run the Upgrade Script

Once the new code is in place, run the upgrade script. You may need to run it
as root, depending on your initial setup. Make sure that the files permissions
are still correct after running the script.
```
# ./scripts/upgrade.sh
```

!!! warning
    The upgrade script will prefer **python3** and **pip3** if both executables
    are available. It can also be forced using the `-3` argument. To force it
    to use **python** and **pip**, use the `-2` argument as below.
```
# ./scripts/upgrade.sh -2
```

What does this script do?

  * installs or upgrades any new required Python dependencies
  * applies any database migrations when required
  * collects static files to be served over HTTP
  * cleans old compiled bytecode

## Restart the WSGI Service

The WSGI service needs to be restart in order to run the new code. Assuming
that you are using **supervisord** like in the setup guide, you can user the
`supervisorctl` command to restart **gunicorn**:
```
# supervisorctl restart peering-manager
```
