#!/usr/bin/python3


import application_killer
import datetime
import logging
import matplotlib.mlab
import numpy as np
import os
import rtlsdr
import sdr.recorder
import sdr.tools


def __get_frequency_power(device, start, stop, **kwargs):
    samples = kwargs["samples"]
    fft = kwargs["fft"]

    device.center_freq = int((start + stop) / 2)
    [powers, frequencies] = matplotlib.mlab.psd(device.read_samples(samples), NFFT=fft, Fs=device.sample_rate)
    return frequencies + device.center_freq, np.log10(powers)


def __detect_best_signal(frequencies, powers, **kwargs):
    noise_level = kwargs["noise_level"]

    i = np.argmax(powers)
    if noise_level <= powers[i]:
        return (int(frequencies[i]), 25000)
    return (None, None)


def __scan(device, **kwargs):
    logger = logging.getLogger("sdr")
    log_frequencies = kwargs["log_frequencies"]
    show_zero_signal = kwargs["show_zero_signal"]
    bandwidth = kwargs["bandwidth"]
    disable_recording = kwargs["disable_recording"]
    noise_level = kwargs["noise_level"]

    printed_any_frequency = False
    for _range in kwargs["frequencies_ranges"]:
        start = _range["start"]
        stop = _range["stop"]
        for substart in range(start, stop, bandwidth):
            frequencies, powers = __get_frequency_power(device, substart, substart + bandwidth, **kwargs)
            (frequency, width) = __detect_best_signal(frequencies, powers, **kwargs)

            if frequency:
                if not disable_recording:
                    sdr.recorder.record(device, frequency, width, _range, **kwargs)

                best_frequencies = np.argsort(powers)
                for i in best_frequencies[-log_frequencies:]:
                    if noise_level <= powers[i]:
                        printed_any_frequency = True
                        logger.debug(sdr.tools.format_frequnecy_power(int(frequencies[i]), float(powers[i])))

    if show_zero_signal and not printed_any_frequency:
        logger.debug(sdr.tools.format_frequnecy_power(0, 0))


def __filter_ranges(**kwargs):
    ranges = []
    logger = logging.getLogger("sdr")
    bandwidth = kwargs["bandwidth"]
    for _range in kwargs["frequencies_ranges"]:
        start = _range["start"]
        stop = _range["stop"]
        if (stop - start) % bandwidth != 0:
            logger.warning(
                "frequency range: %s error! range not fit to bandwidth: %s! skipping!"
                % (sdr.tools.format_frequnecy_range(start, stop), sdr.tools.format_frequnecy(bandwidth))
            )
        else:
            ranges.append(_range)
    if ranges:
        return ranges
    else:
        logger.error("empty frequency ranges! quitting!")
        exit(1)


def run(**kwargs):
    sdr.tools.print_ignored_frequencies(kwargs["ignored_frequencies_ranges"])
    sdr.tools.print_frequencies_ranges(kwargs["frequencies_ranges"])
    sdr.tools.separator("scanning started")
    kwargs["frequencies_ranges"] = __filter_ranges(**kwargs)

    device = rtlsdr.RtlSdr()
    device.ppm_error = kwargs["ppm_error"]
    device.gain = kwargs["tuner_gain"]
    device.sample_rate = kwargs["bandwidth"]

    killer = application_killer.ApplicationKiller()
    while killer.is_running:
        __scan(device, **kwargs)
