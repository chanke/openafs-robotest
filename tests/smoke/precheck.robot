
*** Settings ***
Documentation    Verify the system is ready to run the smoke test.
Library          OperatingSystem
Default Tags     smoke

*** Test Cases ***
AFS is not mounted
    ${mount}=             Run           mount
    Should not contain    ${mount}      AFS on /afs

