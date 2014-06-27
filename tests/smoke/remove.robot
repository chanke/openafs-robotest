
*** Settings ***
Documentation    Remove the OpenAFS server and client binaries.
Library          lib/Install.py
Suite Setup      Installation Setup    ${DIST}

*** Test Cases ***
Remove OpenAFS client
    OpenAFS client is installed
    Remove OpenAFS client
    OpenAFS client is not installed

Remove OpenAFS server
    OpenAFS server is installed
    Remove OpenAFS server
    OpenAFS server is not installed
