from pathlib import Path

from dispread.detect.manual_roi import ManualRoiLocator, quad_from_box
from dispread.frames import open_source
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.sink.jsonl import JsonlSink
from dispread.validate import GateConfig, ReleaseGate


def main():
    # 1. Testbilder generieren: 5 Ziffern 2NAchkommastellen, Einheit N
    source = open_source("synthetic://seven-seg?digits=5&decimals=2&unit=N&count=10&glare=0.9")
    layout = source.layout

    source.open()
    try:
        first_frame = next(iter(source.frames()))
        x, y, width, height = first_frame.raw_metadata["digit_area"]
    finally:
        source.close()

    locator = ManualRoiLocator(
        quad_from_box(x, y, width, height),
        role_hint="main",
        confirmed_by="test_run",
    )

    # ausgabeordner erstellen
    output = Path("var/my_test")
    output.mkdir(parents=True, exist_ok=True)

    # Pipeline definieren. Datenausgabe
    pipeline = Pipeline(
        source=source,
        locator=locator,
        reader=SevenSegmentReader(),
        gate=ReleaseGate(GateConfig(expected_unit="N", confirm_frames=1)),
        sinks=[JsonlSink(output / "values.jsonl")],
        config=PipelineConfig(
            profile_id="my-synthetic-test",
            layout=layout,
        ),
    )

    #  ormatierungsangabe Datenausgabe
    for record in pipeline.run():
        print(
            f"Bild {record.frame_sequence}: "
            f"Wert={record.value}, "
            f"Status={record.status.value}, "
            f"Gründe={record.reject_reasons}"
        )
    print(f"Verarbeitete Bilder: {pipeline.stats.frames}")
    print(f"Statusübersicht: {pipeline.stats.by_status}")
    print(f"Ergebnise: {output / 'values.jsonl'}")


if __name__ == "__main__":
    main()
