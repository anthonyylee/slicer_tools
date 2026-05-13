import argparse

parser = argparse.ArgumentParser(
        prog="Volume_and_photo_scale_calculator",
)

parser.add_argument('-vv', '--volume_vertical')
parser.add_argument('-vh', '--volume_horizontal')
parser.add_argument('-pv', '--photo_vertical')
parser.add_argument('-ph', '--photo_horizontal')

args = parser.parse_args()
#print(args.volume_vertical, args.volume_horizontal, args.photo_vertical, args.photo_horizontal)

vv = float(args.volume_vertical)
vh = float(args.volume_horizontal)
pv = float(args.photo_vertical)
ph = float(args.photo_horizontal)

result = ((vv / pv) + (vh / ph)) / 2
print(f"Factor to scale photo to the same scale as volume (isotropic): {result}")
