CEF Nominal Rolls
=================

Thanks to the members of the [CEFSG](http://cefresearch.ca/), the Nominal
Rolls of the [Canadian Expeditionary
Force](http://en.wikipedia.org/wiki/Canadian_Expeditionary_Force) are
available in digital format for researchers to peruse. Unfortunately, unlike
the [Australian Nominal
Rolls](http://www.awm.gov.au/people/roll-search/nominal_rolls/first_world_war/),
they are images, and thus not easily searchable or readable by computer.

This repository contains code for processing and analyzing the Nominal Rolls,
and hopefully will become a simpler way to browse or search (if everything goes
according to plan.)

Note: Actual Nominal Rolls are not contained in this repository because they
would far exceed GitHub's hosting quota. Please [see the CEFSG
site](http://cefresearch.ca/wiki/index.php/Nominal_Rolls) for information on
obtaining the PDFs.

Requirements
------------

Nominal Rolls are stored locally using [git
annex](https://git-annex.branchable.com/), but due to their size, are not
available here. You will need to download them yourself from the CEFSG site
above if you wish to analyze them.

Scripts are written in Python and may require the following:
  * [lxml](http://lxml.de/)
  * [scikit-learn](http://scikit-learn.org/)
  * [ReportLab](http://www.reportlab.com/opensource/)

Most of these can be installed via your package manager or Python distribution.

Available Scripts
-----------------

`abbyy2pdf.py` converts an ABBYY XML file into a PDF. This script is merely a
test to see what sort of results the OCR process produced. It is not intended
to produce a professional PDF. Characters may be the wrong size or off the
baseline, but the result should give a general idea of the result.

`abbyy2csv.py` converts an ABBYY XML file into a CSV. This script uses the
clustering algorithms of scikit-learn to partition the text data into rows and
columns, and produces a tabular CSV result. The defaults parameters will
likely produce terrible results, though.

`csv2web.py` converts the CSV files into a format suitable for publishing on
GitHub.
