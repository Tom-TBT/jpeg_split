nsplit_x = 4;
nsplit_y = 4;
prefix = "output_"
dir_ = "C:\\Users\\XMG\\Desktop\\moons_jpeg\\";

img_x = 640; //1024 640;
img_y = 640;
newImage("tiled", "RGB", img_x, img_y, 1);
tilled_id = getImageID();


for (i = 0; i < nsplit_y; i++) {
	for (j = 0; j < nsplit_x; j++) {
		tile_path = dir_ + prefix + j + i*nsplit_y + ".jpg";
		open(tile_path);
		//run("Bio-Formats", "open="+tile_path+" color_mode=Default view=Hyperstack stack_order=XYCZT");
		part_id = getImageID();
		Image.copy;
		close();
		selectImage(tilled_id);
		//print(j * (img_x/nsplit_x) + " " + i * (img_y/nsplit_y));
		Image.paste(j * (img_x/nsplit_x), i * (img_y/nsplit_y));
	}
}

src_name = "full-moon-ocean-photo-crop.jpg";
src_path = dir_ + src_name
//run("Bio-Formats", "open="+src_path+" color_mode=Default view=Hyperstack stack_order=XYCZT");
open(dir_ + src_name);
src_id = getImageID();
imageCalculator("Subtract create", src_name, "tiled");
selectImage(tilled_id);
close();
selectImage(src_id);
close();