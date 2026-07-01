from __future__ import print_function

from collections import OrderedDict
import os
import cv2 as cv
import numpy as np
import imutils
import pickle

#for still images, check image inputs

EXPOS_COMP_CHOICES = OrderedDict()
EXPOS_COMP_CHOICES['gain_blocks'] = cv.detail.ExposureCompensator_GAIN_BLOCKS
EXPOS_COMP_CHOICES['gain'] = cv.detail.ExposureCompensator_GAIN
EXPOS_COMP_CHOICES['channel'] = cv.detail.ExposureCompensator_CHANNELS
EXPOS_COMP_CHOICES['channel_blocks'] = cv.detail.ExposureCompensator_CHANNELS_BLOCKS
EXPOS_COMP_CHOICES['no'] = cv.detail.ExposureCompensator_NO

BA_COST_CHOICES = OrderedDict()
BA_COST_CHOICES['ray'] = cv.detail_BundleAdjusterRay
BA_COST_CHOICES['reproj'] = cv.detail_BundleAdjusterReproj
BA_COST_CHOICES['affine'] = cv.detail_BundleAdjusterAffinePartial
BA_COST_CHOICES['no'] = cv.detail_NoBundleAdjuster

FEATURES_FIND_CHOICES = OrderedDict()
try:
    cv.xfeatures2d_SURF.create() # check if the function can be called
    FEATURES_FIND_CHOICES['surf'] = cv.xfeatures2d_SURF.create
except (AttributeError, cv.error) as e:
    print("SURF not available")
# if SURF not available, ORB is default
FEATURES_FIND_CHOICES['orb'] = cv.ORB.create
try:
    FEATURES_FIND_CHOICES['sift'] = cv.SIFT_create
except AttributeError:
    print("SIFT not available")
try:
    FEATURES_FIND_CHOICES['brisk'] = cv.BRISK_create
except AttributeError:
    print("BRISK not available")
try:
    FEATURES_FIND_CHOICES['akaze'] = cv.AKAZE_create
except AttributeError:
    print("AKAZE not available")

SEAM_FIND_CHOICES = OrderedDict()
SEAM_FIND_CHOICES['gc_color'] = cv.detail_GraphCutSeamFinder('COST_COLOR')
SEAM_FIND_CHOICES['gc_colorgrad'] = cv.detail_GraphCutSeamFinder('COST_COLOR_GRAD')
SEAM_FIND_CHOICES['dp_color'] = cv.detail_DpSeamFinder('COLOR')
SEAM_FIND_CHOICES['dp_colorgrad'] = cv.detail_DpSeamFinder('COLOR_GRAD')
SEAM_FIND_CHOICES['voronoi'] = cv.detail.SeamFinder_createDefault(cv.detail.SeamFinder_VORONOI_SEAM)
SEAM_FIND_CHOICES['no'] = cv.detail.SeamFinder_createDefault(cv.detail.SeamFinder_NO)

ESTIMATOR_CHOICES = OrderedDict()
ESTIMATOR_CHOICES['homography'] = cv.detail_HomographyBasedEstimator
ESTIMATOR_CHOICES['affine'] = cv.detail_AffineBasedEstimator

WARP_CHOICES = (
    'spherical',
    'plane',
    'affine',
    'cylindrical',
    'fisheye',
    'stereographic',
    'compressedPlaneA2B1',
    'compressedPlaneA1.5B1',
    'compressedPlanePortraitA2B1',
    'compressedPlanePortraitA1.5B1',
    'paniniA2B1',
    'paniniA1.5B1',
    'paniniPortraitA2B1',
    'paniniPortraitA1.5B1',
    'mercator',
    'transverseMercator',
)

WAVE_CORRECT_CHOICES = OrderedDict()
WAVE_CORRECT_CHOICES['horiz'] = cv.detail.WAVE_CORRECT_HORIZ
WAVE_CORRECT_CHOICES['no'] = None
WAVE_CORRECT_CHOICES['vert'] = cv.detail.WAVE_CORRECT_VERT

BLEND_CHOICES = ('multiband', 'feather', 'no',)


def get_matcher(matcher_type = "homography"):
    """
    Returns the selected feature matcher.
    """
    try_cuda = False #args.try_cuda
    #matcher_type = 'homography' #args.matcher
    match_conf = 0.3 #0.3 #or 0.65 if not orb nor akaze

    if matcher_type == "flann":
        index_params = dict(algorithm=1, trees=5)  # KDTree for float descriptors (like SIFT, AKAZE)
        search_params = dict(checks=50)
        matcher = cv.FlannBasedMatcher(index_params, search_params)
    elif matcher_type == "brute_force":
        matcher = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=True)  #for AKAZE, ORB
        # matcher = cv.BFMatcher(cv.NORM_L2, crossCheck=True)  #for SIFT, SURF
    elif matcher_type == "affine":
        matcher = cv.detail_AffineBestOf2NearestMatcher(False, try_cuda, match_conf)
    else:  # Default to homography matcher
        matcher = cv.detail_BestOf2NearestMatcher(try_cuda, match_conf)

    return matcher


def get_compensator():
    expos_comp_type = EXPOS_COMP_CHOICES['gain_blocks'] #EXPOS_COMP_CHOICES['gain_blocks'] #EXPOS_COMP_CHOICES[args.expos_comp]
    expos_comp_nr_feeds = 1 #args.expos_comp_nr_feeds
    expos_comp_block_size = 32 #args.expos_comp_block_size
    # expos_comp_nr_filtering = args.expos_comp_nr_filtering
    if expos_comp_type == cv.detail.ExposureCompensator_CHANNELS:
        compensator = cv.detail_ChannelsCompensator(expos_comp_nr_feeds)
        # compensator.setNrGainsFilteringIterations(expos_comp_nr_filtering)
    elif expos_comp_type == cv.detail.ExposureCompensator_CHANNELS_BLOCKS:
        compensator = cv.detail_BlocksChannelsCompensator(
            expos_comp_block_size, expos_comp_block_size,
            expos_comp_nr_feeds
        )
        # compensator.setNrGainsFilteringIterations(expos_comp_nr_filtering)
    else:
        compensator = cv.detail.ExposureCompensator_createDefault(expos_comp_type)
    return compensator


def main():
    start_time = cv.getTickCount()
    #args = parser.parse_args()

    #mimic iteration

    image_folder = "images3"
    img_names = sorted([ # Get all image file paths
        os.path.join(image_folder, f) for f in os.listdir(image_folder) 
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])#args.img_names
    print(img_names)
    work_megapix = 0.6 #0.6 #args.work_megapix
    seam_megapix = 0.1 #0.1 #args.seam_megapix
    compose_megapix = 0.6 #args.compose_megapix
    conf_thresh = 1.0 #args.conf_thresh
    ba_refine_mask = 'xxxxx' #args.ba_refine_mask
    wave_correct = WAVE_CORRECT_CHOICES['horiz'] #WAVE_CORRECT_CHOICES[args.wave_correct] horiz
    # camera alignment might be helpful to set it to no wave correct, speeding up the pipeline
    save_graph = None #
    if save_graph is None:
        save_graph = False
    else:
        save_graph = True
    warp_type = "cylindrical"#WARP_CHOICES[0] #args.warp
    blend_type = BLEND_CHOICES[0]#BLEND_CHOICES[0] #args.blend
    blend_strength = 5 #args.blend_strength
    result_name = 'result.jpg' #args.output
    result_name_o = 'resultyy.jpg'
    timelapse = None #
    if timelapse is not None:
        timelapse = True
        if timelapse == "as_is":
            timelapse_type = cv.detail.Timelapser_AS_IS
        elif timelapse == "crop":
            timelapse_type = cv.detail.Timelapser_CROP
        else:
            print("Bad timelapse method")
            exit()
    else:
        timelapse = False
    finder = FEATURES_FIND_CHOICES['orb'](
    nfeatures=3400,       # 500 More keypoints for better matching
    scaleFactor=1.1,      # 1.2 Smaller scaling for finer feature detection
    nlevels=6,           # 8 More levels for robustness
    edgeThreshold=12,     # 31 Detect keypoints closer to edges
    WTA_K=2,              # 2 Use 3-point BRIEF descriptor
    scoreType=cv.ORB_FAST_SCORE,  # HARRIS Use FAST scoring instead of Harris
    patchSize=31,         # 31 Default patch size
    fastThreshold=12      # 20 Lower threshold to detect more keypoints
) #cv.ORB.create(nfeatures=500)  #FEATURES_FIND_CHOICES[args.features]()

    """finder = FEATURES_FIND_CHOICES['akaze'](
    descriptor_type=cv.AKAZE_DESCRIPTOR_KAZE_UPRIGHT,  # MLDB Type of descriptor (MLDB or KAZE)
    descriptor_size=0,  # 0 Descriptor size (0 = default 486 bits)
    descriptor_channels=3,  # 3 Number of channels (1, 2, or 3)
    threshold=0.0001,  # 0.001 Detector response threshold (lower = more keypoints)
    nOctaves=4,  # 4 Number of scale levels
    nOctaveLayers=4,  # 4 Number of sublevels per octave
    diffusivity=cv.KAZE_DIFF_PM_G2  # KAZE DIFF PM G2 Diffusion type (affects smoothing)
)"""

    """finder = FEATURES_FIND_CHOICES['sift'](
    nfeatures=4000,  # 500 More keypoints for robustness
    nOctaveLayers=7,  # 3 More layers per octave = better scale invariance
    contrastThreshold=0.0001,  # 0.04 Lower contrast threshold = more keypoints
    edgeThreshold=20,  # 10 Detect more edge features
    sigma=1.8  # 1.6 Slightly lower Gaussian blur for sharper features
)"""

    """finder = FEATURES_FIND_CHOICES['brisk'](
    thresh=22,  # 30 FAST threshold (lower = more keypoints)
    octaves=3,  # 3 Number of pyramid octaves
    patternScale=1.0  # 1.0 Scale of sampling pattern
)""" #fastest??? faster with horiz wave correct

    seam_work_aspect = 1
    full_img_sizes = []
    features = []
    images = []
    is_work_scale_set = False
    is_seam_scale_set = False
    is_compose_scale_set = False
    stretchratio = 1
    for name in img_names:
        full_img = cv.imread(cv.samples.findFile(name))
        if full_img is None:
            print("Cannot read image ", name)
            exit()
        full_img_sizes.append((full_img.shape[1], full_img.shape[0]))
        if work_megapix < 0:
            img = full_img
            work_scale = 1
            is_work_scale_set = True
        else:
            if is_work_scale_set is False:
                work_scale = min(1.0, np.sqrt(work_megapix * 1e6 / (full_img.shape[0] * full_img.shape[1])))
                is_work_scale_set = True
            img = cv.resize(src=full_img, dsize=None, fx=stretchratio*work_scale, fy=work_scale, interpolation=cv.INTER_LINEAR_EXACT)
        if is_seam_scale_set is False:
            if seam_megapix > 0:
                seam_scale = min(1.0, np.sqrt(seam_megapix * 1e6 / (full_img.shape[0] * full_img.shape[1])))
            else:
                seam_scale = 1.0
            seam_work_aspect = seam_scale / work_scale
            is_seam_scale_set = True
        img_feat = cv.detail.computeImageFeatures2(finder, img)
        features.append(img_feat)
        img = cv.resize(src=full_img, dsize=None, fx=stretchratio*seam_scale, fy=seam_scale, interpolation=cv.INTER_LINEAR_EXACT)
        images.append(img)

    matcher_type = "homography"
    matcher = get_matcher(matcher_type) #modify the get_matcher
    

    if matcher_type == "homography":
        p = matcher.apply2(features)
        matcher.collectGarbage()

    elif matcher_type == "flann":
        # Extract descriptors from features
        descriptors = [f.descriptors for f in features]

# Perform feature matching
        p = []
        #matcher = get_matcher("flann")  # Change to "brute_force" for BFMatcher

        for i in range(len(descriptors) - 1):
            if descriptors[i] is not None and descriptors[i+1] is not None:
                matches = matcher.knnMatch(descriptors[i], descriptors[i+1], k=2)
                good_matches = []
                for m, n in matches:
                    if m.distance < 0.7 * n.distance:
                        good_matches.append(m)

                p.append(good_matches)
    

    #if save_graph:
    #    with open(None, 'w') as fh:
    #        fh.write(cv.detail.matchesGraphAsString(img_names, p, conf_thresh))

    indices = cv.detail.leaveBiggestComponent(features, p, conf_thresh)
    img_subset = []
    img_names_subset = []
    full_img_sizes_subset = []
    for i in range(len(indices)):
        img_names_subset.append(img_names[indices[i]])
        img_subset.append(images[indices[i]])
        full_img_sizes_subset.append(full_img_sizes[indices[i]])
    images = img_subset
    img_names = img_names_subset
    full_img_sizes = full_img_sizes_subset
    num_images = len(img_names)
    if num_images < 2:
        print("Need more images")
        exit()

    estimator = ESTIMATOR_CHOICES['homography']() #ESTIMATOR_CHOICES[args.estimator]()
    b, cameras = estimator.apply(features, p, None)
    if not b:
        print("Homography estimation failed.")
        exit()
    for cam in cameras:
        cam.R = cam.R.astype(np.float32)

    adjuster = BA_COST_CHOICES['ray']() #BA_COST_CHOICES['ray']() #BA_COST_CHOICES[args.ba]()
    adjuster.setConfThresh(conf_thresh)
    refine_mask = np.zeros((3, 3), np.uint8)
    if ba_refine_mask[0] == 'x':
        refine_mask[0, 0] = 1
    if ba_refine_mask[1] == 'x':
        refine_mask[0, 1] = 1
    if ba_refine_mask[2] == 'x':
        refine_mask[0, 2] = 1
    if ba_refine_mask[3] == 'x':
        refine_mask[1, 1] = 1
    if ba_refine_mask[4] == 'x':
        refine_mask[1, 2] = 1
    adjuster.setRefinementMask(refine_mask)
    b, cameras = adjuster.apply(features, p, cameras)
    if not b:
        print("Camera parameters adjusting failed.")
        exit()

    # Save the camera parameters to disk
    camera_data = []
    for cam in cameras:
        cam_info = {
            "focal": cam.focal,
            "aspect": cam.aspect,
            "ppx": cam.ppx,
            "ppy": cam.ppy,
            "R": cam.R.tolist(),   # convert numpy array to list
            "t": cam.t.tolist()
        }
        camera_data.append(cam_info)

    # Save to file
    with open('camera_params.pkl', 'wb') as f:
        pickle.dump(camera_data, f)

    print("Saved camera parameters to camera_params.pkl")

    focals = []
    for cam in cameras:
        focals.append(cam.focal)
    focals.sort()
    if len(focals) % 2 == 1:
        warped_image_scale = focals[len(focals) // 2]
    else:
        warped_image_scale = (focals[len(focals) // 2] + focals[len(focals) // 2 - 1]) / 2
    if wave_correct is not None:
        rmats = []
        for cam in cameras:
            rmats.append(np.copy(cam.R))
        rmats = cv.detail.waveCorrect(rmats, wave_correct)
        for idx, cam in enumerate(cameras):
            cam.R = rmats[idx]
    corners = []
    masks_warped = []
    images_warped = []
    sizes = []
    masks = []
    for i in range(0, num_images):
        um = cv.UMat(255 * np.ones((images[i].shape[0], images[i].shape[1]), np.uint8))
        masks.append(um)

    warper = cv.PyRotationWarper(warp_type, warped_image_scale * seam_work_aspect)  # warper could be nullptr?
    for idx in range(0, num_images):
        K = cameras[idx].K().astype(np.float32)
        swa = seam_work_aspect
        K[0, 0] *= swa
        K[0, 2] *= swa
        K[1, 1] *= swa
        K[1, 2] *= swa
        corner, image_wp = warper.warp(images[idx], K, cameras[idx].R, cv.INTER_LINEAR, cv.BORDER_REFLECT)
        corners.append(corner)
        sizes.append((image_wp.shape[1], image_wp.shape[0]))
        images_warped.append(image_wp)
        p, mask_wp = warper.warp(masks[idx], K, cameras[idx].R, cv.INTER_NEAREST, cv.BORDER_CONSTANT)
        masks_warped.append(mask_wp.get())

    images_warped_f = []
    for img in images_warped:
        imgf = img.astype(np.float32)
        images_warped_f.append(imgf)

    compensator = get_compensator() # modify
    compensator.feed(corners=corners, images=images_warped, masks=masks_warped)

    seam_finder = SEAM_FIND_CHOICES['gc_color'] #SEAM_FIND_CHOICES[args.seam]
    masks_warped = seam_finder.find(images_warped_f, corners, masks_warped)
    compose_scale = 1
    corners = []
    sizes = []
    blender = None
    timelapser = None
    # https://github.com/opencv/opencv/blob/4.x/samples/cpp/stitching_detailed.cpp#L725 ?
    for idx, name in enumerate(img_names):
        full_img = cv.imread(name)
        if not is_compose_scale_set:
            if compose_megapix > 0:
                compose_scale = min(1.0, np.sqrt(compose_megapix * 1e6 / (full_img.shape[0] * full_img.shape[1])))
            is_compose_scale_set = True
            compose_work_aspect = compose_scale / work_scale
            warped_image_scale *= compose_work_aspect
            warper = cv.PyRotationWarper(warp_type, warped_image_scale)
            for i in range(0, len(img_names)):
                cameras[i].focal *= compose_work_aspect
                cameras[i].ppx *= compose_work_aspect
                cameras[i].ppy *= compose_work_aspect
                sz = (int(round(full_img_sizes[i][0] * compose_scale)),
                      int(round(full_img_sizes[i][1] * compose_scale)))
                K = cameras[i].K().astype(np.float32)
                roi = warper.warpRoi(sz, K, cameras[i].R)
                corners.append(roi[0:2])
                sizes.append(roi[2:4])
        if abs(compose_scale - 1) > 1e-1:
            img = cv.resize(src=full_img, dsize=None, fx=stretchratio*compose_scale, fy=compose_scale,
                            interpolation=cv.INTER_LINEAR_EXACT)
        else:
            img = full_img
        _img_size = (img.shape[1], img.shape[0])
        K = cameras[idx].K().astype(np.float32)
        corner, image_warped = warper.warp(img, K, cameras[idx].R, cv.INTER_LINEAR, cv.BORDER_REFLECT)
        mask = 255 * np.ones((img.shape[0], img.shape[1]), np.uint8)
        p, mask_warped = warper.warp(mask, K, cameras[idx].R, cv.INTER_NEAREST, cv.BORDER_CONSTANT)
        compensator.apply(idx, corners[idx], image_warped, mask_warped)
        image_warped_s = image_warped.astype(np.int16)
        dilated_mask = cv.dilate(masks_warped[idx], None)
        seam_mask = cv.resize(dilated_mask, (mask_warped.shape[1], mask_warped.shape[0]), 0, 0, cv.INTER_LINEAR_EXACT)
        mask_warped = cv.bitwise_and(seam_mask, mask_warped)
        if blender is None and not timelapse:
            blender = cv.detail.Blender_createDefault(cv.detail.Blender_NO)
            dst_sz = cv.detail.resultRoi(corners=corners, sizes=sizes)
            blend_width = np.sqrt(dst_sz[2] * dst_sz[3]) * blend_strength / 100
            if blend_width < 1:
                blender = cv.detail.Blender_createDefault(cv.detail.Blender_NO)
            elif blend_type == "multiband":
                blender = cv.detail_MultiBandBlender()
                blender.setNumBands((np.log(blend_width) / np.log(2.) - 1.).astype(np.int32))
            elif blend_type == "feather":
                blender = cv.detail_FeatherBlender()
                blender.setSharpness(1. / blend_width)
            blender.prepare(dst_sz)
        elif timelapser is None and timelapse:
            timelapser = cv.detail.Timelapser_createDefault(timelapse_type)
            timelapser.initialize(corners, sizes)
        if timelapse:
            ma_tones = np.ones((image_warped_s.shape[0], image_warped_s.shape[1]), np.uint8)
            timelapser.process(image_warped_s, ma_tones, corners[idx])
            pos_s = img_names[idx].rfind("/")
            if pos_s == -1:
                fixed_file_name = "fixed_" + img_names[idx]
            else:
                fixed_file_name = img_names[idx][:pos_s + 1] + "fixed_" + img_names[idx][pos_s + 1:]
            cv.imwrite(fixed_file_name, timelapser.getDst())
        else:
            blender.feed(cv.UMat(image_warped_s), mask_warped, corners[idx])
    if not timelapse:
        result = None
        result_mask = None
        result, result_mask = blender.blend(result, result_mask)
        cv.imwrite(result_name_o, cv.normalize(result, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U))
        #result = remove_black_borders(cv.normalize(result, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U))
        #cv.imwrite(result_name, result)
        #zoom_x = 600.0 / result.shape[1]
        #dst = cv.normalize(src=result, dst=None, alpha=255., norm_type=cv.NORM_MINMAX, dtype=cv.CV_8U)
        #dst = cv.resize(dst, dsize=None, fx=zoom_x, fy=zoom_x)
        #cv.imshow(result_name, dst)
        cv.waitKey()

    print("Done")
    end_time = cv.getTickCount()
    execution_time = (end_time - start_time) / cv.getTickFrequency()
    print(f"Execution Time: {execution_time:.6f} seconds")


if __name__ == '__main__':
    main()
    cv.destroyAllWindows()
