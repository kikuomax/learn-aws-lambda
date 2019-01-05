.. Learn AWS Lambda documentation master file, created by
   sphinx-quickstart on Fri Jan  4 10:19:11 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Learn AWS Lambda's documentation!
============================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


lambda_function_4
=================

Environment Variables
---------------------

This function accepts the following environment variables,

``COMPREHEND_S3_LOGGING_LEVEL``
    Logging level of the function. "INFO" by default.

``COMPREHEND_REGION``
    Region where Amazon Comprehend is hosted. "us-east-2" by default.

``COMPREHEND_S3_OUTPUT_BUCKET``
    Name of the bucket where analysis results are saved. The same bucket as an input object by default.

``COMPREHEND_S3_OUTPUT_FOLDER``
    Path of a folder where analysis results are saved. "comprehend" by default. Trailing slashes ('/') are removed.

Functions
---------

.. automodule:: lambda_function_4
   :members:

