FROM ubuntu:16.04

# Install python
RUN apt-get update && \
    apt-get install -y python python-dev python-pip

# Install Supervisord
RUN apt-get install -y supervisor

# Install software-properties-common for add-apt-repository
RUN apt-get install -y software-properties-common

# Add the trysty-media PPA
#RUN add-apt-repository -y ppa:mc3man/trusty-media

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Install other required packages
RUN apt-get install -y openjdk-8-jre libfreetype6-dev libpng-dev libxft-dev libopencv-dev \
python-opencv gfortran libopenblas-dev liblapack-dev libffi-dev libssl-dev build-essential \
git vim \
&& apt-get autoremove -y \
&& rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/include/freetype2 /usr/local/include/freetype

RUN mkdir /preview-bot

# This is done so that it doesn't re-install the requirements every time
# a file is changed, but instead uses the cache
COPY ./preview-bot/requirements.txt /preview-bot/requirements.txt

WORKDIR /preview-bot
RUN pip install -r requirements.txt

COPY ./preview-bot /preview-bot

COPY ./libs/liquibase-3.5.3-bin.tar.gz /preview-bot/libs/

RUN tar zxf /preview-bot/libs/liquibase-3.5.3-bin.tar.gz -C /preview-bot/libs/liquibase/

COPY ./libs/sqlite-jdbc-3.14.2.1.jar /preview-bot/libs/liquibase/lib/

# Custom Supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["/usr/bin/supervisord"]

