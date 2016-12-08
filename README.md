## bacula_stats
Displays most recent successful job for each client's fileset pools on one page and additionally compares it to your
configured jobs to show by markup, whether a backup is missing. Moreover you can configure for defined pools a timeout
value (in days), after that the backup should be marked up as old (yellow). Your config file (you have to specify the
path in functions.py) will be parsed for the configured clients and thus checked for connectivity on port 9102, to
indicate whether your client's bacula service is up or down. Besides printing the recent backups you can also tell
bacula_stats to print all backups to the console.

bacula_stats is the CLI version of bacula_monitor. It is easier deployable, distributable and more secure than
bacula_monitor.


## Install
`pip3 install bacula_stats`

## Configuration
See etc/bacula_stats.conf as an example for your config file.

## Usage
```
usage: bacula_stats [-h] [-a] [-r]                                                                                                                                                             
                                                                                                                                                                                               
bacula_stats - Display recent and all backups.                                                                                                                                                 
                                                                                                                                                                                               
optional arguments:                                                                                                                                                                            
  -h, --help    show this help message and exit                                                                                                                                                
  -a, --all     Return all backups.                                                                                                                                                            
  -r, --recent  Return recent backups
```
Preferably pipe bacula_stats to `less` to have scroll conveniently through your backup stats:
`bacula_stats |less -R --tilde`
In your .bashrc put:
```
function bacula_stats() {
  /usr/bin/bacula_stats "$@" | less --tilde -R
}
```

