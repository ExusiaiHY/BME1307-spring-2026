function export_busat_masks(dataDir, outputDir)
%EXPORT_BUSAT_MASKS Export BUSAT autosegment masks for the Part 2 dataset.
%   Usage in MATLAB:
%       export_busat_masks
%       export_busat_masks(dataDir, outputDir)
%
%   The script expects BUSAT to already be on the MATLAB path. It reads each
%   JPG in the Part 2 dataset, runs AUTOSEGMENT on the grayscale ROI, and
%   writes binary PNG masks named <image_id>_mask.png so the Python pipeline
%   can evaluate them with:
%
%       python scripts/run_part2.py --strategies busat --busat-masks-dir outputs/part2/busat_masks

if nargin < 1 || isempty(dataDir)
    projectRoot = fileparts(fileparts(mfilename('fullpath')));
    dataDir = fullfile(projectRoot, 'Breast-ultrasound-samples', 'Ultrasound Samples');
end
if nargin < 2 || isempty(outputDir)
    projectRoot = fileparts(fileparts(mfilename('fullpath')));
    outputDir = fullfile(projectRoot, 'outputs', 'part2', 'busat_masks');
end

if exist('autosegment', 'file') ~= 2
    error(['AUTOSEGMENT not found on MATLAB path. ' ...
           'Open RUN_ME_FIRST.m inside the BUSAT toolbox or add the BUSAT folders manually.']);
end

if ~exist(dataDir, 'dir')
    error('Data directory does not exist: %s', dataDir);
end
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

files = dir(fullfile(dataDir, '*.jpg'));
fprintf('[busat] exporting %d masks from %s to %s\n', numel(files), dataDir, outputDir);

for i = 1:numel(files)
    fileName = files(i).name;
    filePath = fullfile(files(i).folder, fileName);
    [~, stem, ~] = fileparts(fileName);

    I = imread(filePath);
    if ndims(I) == 3
        I = rgb2gray(I);
    end

    [~, BW] = autosegment(I);
    maskPath = fullfile(outputDir, sprintf('%s_mask.png', stem));
    imwrite(uint8(BW) * 255, maskPath);
    fprintf('[busat] %3d/%3d  %s -> %s\n', i, numel(files), fileName, maskPath);
end
end
