import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="improved-camera-control",
    version="0.0.0",
    author="Sam Tran",
    author_email="sam.tran.qu@gmail.com",
    description="An improved GUI and camera capture logic based on aniposelib and Matthis's lab camera GUI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/samsam2610/Improved-camera-control",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Image Recognition"
    ],
    install_requires=[
        'opencv-contrib-python==4.6.0.68',
        'numba', 'pandas',
        'numpy==1.19.2', 'scipy', 'toml', 'tqdm', 'Click'
    ],
    extras_require={
        'full':  ["checkerboard"]
    }
)
