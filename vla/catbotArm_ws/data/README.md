---
license: apache-2.0
task_categories:
- robotics
tags:
- LeRobot
configs:
- config_name: default
  data_files: data/*/*.parquet
---

This dataset was created using [LeRobot](https://github.com/huggingface/lerobot).

## Dataset Description



- **Homepage:** [More Information Needed]
- **Paper:** [More Information Needed]
- **License:** apache-2.0

## Dataset Structure

[meta/info.json](meta/info.json):
```json
{
    "codebase_version": "v3.0",
    "robot_type": "so_follower",
    "total_episodes": 4,
    "total_frames": 4181,
    "total_tasks": 4,
    "chunks_size": 1000,
    "data_files_size_in_mb": 100,
    "video_files_size_in_mb": 200,
    "fps": 30,
    "splits": {
        "train": "0:4"
    },
    "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
    "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
    "features": {
        "action": {
            "dtype": "float32",
            "names": [
                "shoulder_pan.pos",
                "shoulder_lift.pos",
                "elbow_flex.pos",
                "wrist_flex.pos",
                "wrist_roll.pos",
                "gripper.pos"
            ],
            "shape": [
                6
            ]
        },
        "observation.state": {
            "dtype": "float32",
            "names": [
                "shoulder_pan.pos",
                "shoulder_lift.pos",
                "elbow_flex.pos",
                "wrist_flex.pos",
                "wrist_roll.pos",
                "gripper.pos"
            ],
            "shape": [
                6
            ]
        },
        "timestamp": {
            "dtype": "float32",
            "shape": [
                1
            ],
            "names": null
        },
        "frame_index": {
            "dtype": "int64",
            "shape": [
                1
            ],
            "names": null
        },
        "episode_index": {
            "dtype": "int64",
            "shape": [
                1
            ],
            "names": null
        },
        "index": {
            "dtype": "int64",
            "shape": [
                1
            ],
            "names": null
        },
        "task_index": {
            "dtype": "int64",
            "shape": [
                1
            ],
            "names": null
        }
    }
}
```


## Citation

**BibTeX:**

```bibtex
[More Information Needed]
```