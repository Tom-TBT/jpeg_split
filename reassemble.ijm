nsplit_x = 4;
nsplit_y = 4;
prefix = "output_"
dir_test = "C:\\Users\\XMG\\Documents\\Github\\jpeg_split\\test_images\\";
dir_ = "C:\\Users\\XMG\\Documents\\Github\\jpeg_split\\output\\";

img_x = 2560; //1024 640;
img_y = 2560;
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

src_name = "NGC6888.jpg";
src_path = dir_test + src_name
//run("Bio-Formats", "open="+src_path+" color_mode=Default view=Hyperstack stack_order=XYCZT");
open(src_path);
src_id = getImageID();
imageCalculator("Subtract create", src_name, "tiled");
selectImage(tilled_id);
close();
selectImage(src_id);
close();