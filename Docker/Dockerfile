FROM tensorflow/tensorflow:1.15.0-gpu

RUN pip install keras matplotlib scikit-learn pandas bokeh pydot holoviews librosa scikit-image moviepy tensorflow-graphics-gpu
RUN apt update && apt-get install -y graphviz
RUN pip install comet-ml
RUN pip install opencv-python
#morecvutils
RUN pip install tensorflow-datasets
