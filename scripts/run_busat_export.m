% RUN_BUSAT_EXPORT Bootstrap wrapper that loads BUSAT then exports masks.
%   Usage: matlab -batch "run('scripts/run_busat_export.m')"

scriptDir = fileparts(mfilename('fullpath'));
projectRoot = fileparts(scriptDir);
busatDir = fullfile(projectRoot, 'US Toolbox Ver. 2.0');
if ~exist(busatDir, 'dir')
    error('BUSAT toolbox folder not found at: %s', busatDir);
end
oldDir = pwd;
cleanupObj = onCleanup(@() cd(oldDir));
cd(busatDir);
run('RUN_ME_FIRST.m');
cd(oldDir);

addpath(scriptDir);
dataDir = fullfile(projectRoot, 'Breast-ultrasound-samples', 'Ultrasound Samples');
outDir  = fullfile(projectRoot, 'outputs', 'part2', 'busat_masks');

% BUSAT's texturefeats opens and closes a parpool every single image, which
% dominates run time. Pre-open a persistent pool so s=false inside the
% toolbox and the pool is not deleted between images.
if license('test', 'Distrib_Computing_Toolbox') && isempty(gcp('nocreate'))
    try
        parpool('Processes', feature('numCores'));
    catch ME
        warning('Failed to pre-open parpool: %s', ME.message);
    end
end

export_busat_masks(dataDir, outDir);

if ~isempty(gcp('nocreate'))
    delete(gcp('nocreate'));
end
