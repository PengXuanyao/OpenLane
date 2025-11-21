__DIRNAME__ := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

export OPENLANE_IMAGE_NAME ?= crpi-2kgy25fd8woahuci.cn-beijing.personal.cr.aliyuncs.com/registry-pxy/openlane:v1.0
