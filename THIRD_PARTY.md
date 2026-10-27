# Third-party software and data

The tracker installs these with Setup.bat. They are not bundled in this repository.

| package | licence | used for |
|---|---|---|
| [RapidOCR](https://github.com/RapidAI/RapidOCR) | Apache 2.0 | reading tooltip text (its models come from PaddleOCR, Apache 2.0) |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT | running the OCR models |
| [OpenCV](https://opencv.org) (opencv-python-headless) | Apache 2.0 | image handling |
| [NumPy](https://numpy.org) | BSD 3-Clause | number crunching |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | MIT | matching names |
| [python-mss](https://github.com/BoboTiG/python-mss) | MIT | screen capture |
| [DXcam](https://github.com/ra1nty/DXcam) | MIT | fast screen capture on Windows |

Item data and prices are fetched at run time from
[api.star-citizen.wiki](https://star-citizen.wiki) (prices there come from
[UEX](https://uexcorp.space)). Nothing from either is stored in this repository.

Star Citizen game text is read from the player's own installation and never
copied into this repository. Star Citizen is a trademark of Cloud Imperium
Rights LLC; this project isn't affiliated with or endorsed by Cloud Imperium Games.
