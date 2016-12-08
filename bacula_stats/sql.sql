## Correct one:
SELECT c.name, p.name, j.jobbytes, j.realendtime, j.starttime, j.jobfiles 
                     FROM client c 
                     LEFT JOIN LATERAL ( 
                       SELECT DISTINCT ON (j.poolid) j.jobbytes, j.realendtime, j.poolid,  j.starttime, j.jobfiles 
                       FROM job j 
                       WHERE j.clientid = c.clientid  AND j.jobstatus IN ('T', 'W') AND j.level IN ('F', 'I', 'D') AND j.type IN ('B', 'C') 
                       ORDER BY j.poolid, j.realendtime DESC 
                     ) j ON TRUE 
                     LEFT JOIN pool p ON p.poolid = j.poolid;



## Another attempt probably wrong:
SELECT DISTINCT ON (j.clientid, j.poolid) c.name, p.name, j.jobbytes, j.realendtime, j.starttime, j.jobfiles
  FROM job j
  LEFT JOIN client c  ON c.clientid = j.clientid
  LEFT JOIN pool p  ON p.poolid = j.poolid
  WHERE j.jobstatus IN ('T', 'W') AND j.level IN ('F', 'I', 'D') AND j.type IN ('B', 'C')
  ORDER BY j.clientid, j.poolid, j.realendtime DESC
