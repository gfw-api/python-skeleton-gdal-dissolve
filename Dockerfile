###############################################################
# This is a Conda/Python 3.6/GDAL build based on:
# https://hub.docker.com/r/conda/miniconda3/~/dockerfile/
###############################################################

FROM debian:jessie-slim
MAINTAINER David Eitelberg, deitelberg@blueraster.com

ENV NAME ps
ENV USER ps

RUN apt-get -qq update && apt-get -qq -y install curl bzip2 \
    && curl -sSL https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -bfp /usr/local \
    && rm -rf /tmp/miniconda.sh \
    && apt-get -qq -y remove curl bzip2 \
    && apt-get -qq -y autoremove \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* /var/log/dpkg.log \
    && conda clean --all --yes

RUN mkdir -p /opt/$NAME
COPY environment-ubuntu.yml /opt/$NAME/environment.yml
ENV PATH /usr/local/envs/gfw-api/bin:$PATH

RUN groupadd $USER && useradd -g $USER $USER -s /bin/bash
RUN conda update conda
RUN conda config --add channels conda-forge 
RUN conda config --set always_yes yes --set changeps1 no
RUN cd /opt/$NAME && conda env create -f environment.yml

COPY entrypoint.sh /opt/$NAME/entrypoint.sh
COPY main.py /opt/$NAME/main.py
COPY gunicorn.py /opt/$NAME/gunicorn.py

# Copy the application folder inside the container
WORKDIR /opt/$NAME

COPY ./$NAME /opt/$NAME/$NAME
COPY ./microservice /opt/$NAME/microservice
RUN chown -R $USER:$USER /opt/$NAME

# Tell Docker we are going to use this ports
EXPOSE 5800
USER $USER

# Run unit tests
#ENTRYPOINT ["/bin/bash", "-c"]
#RUN ["/bin/bash", "-c", "source activate gfw-api && exec pytest -v && source deactivate"]

# Launch script
ENTRYPOINT ["./entrypoint.sh"]
