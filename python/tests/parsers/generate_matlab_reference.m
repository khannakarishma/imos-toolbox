%% generate_matlab_reference.m
% Generates reference .mat files from MATLAB parsers for regression testing.
%
% Run this script from the imos-toolbox ROOT directory:
%   cd C:\path\to\imos-toolbox\imos-toolbox
%   run('python/tests/parsers/generate_matlab_reference.m')
%
% Output: .mat files saved to python/tests/parsers/data/matlab_reference/
%
% Each .mat file contains the full sample_data struct from the parser.

%% Setup paths
toolboxRoot = pwd;
addpath(genpath(toolboxRoot));

outputDir = fullfile(toolboxRoot, 'python', 'tests', 'parsers', 'data', 'matlab_reference');
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

dataRoot = fullfile(toolboxRoot, 'python', 'tests', 'parsers', 'data', 'sbe');

fprintf('=== MATLAB Reference Generation for Family A ===\n');
fprintf('Toolbox root: %s\n', toolboxRoot);
fprintf('Output dir:   %s\n', outputDir);
fprintf('\n');

%% SBE19 - SBE19plus_parser1.cnv
fprintf('--- SBE19 ---\n');
try
    file = fullfile(dataRoot, 'sbe19', 'SBE19plus_parser1.cnv');
    fprintf('  Parsing: %s\n', file);
    sample_data = SBE19Parse({file}, 'timeSeries');
    save(fullfile(outputDir, 'SBE19_SBE19plus_parser1_timeSeries.mat'), 'sample_data');
    fprintf('  OK: %d variables, %d time samples\n', ...
        length(sample_data.variables), length(sample_data.dimensions{1}.data));
catch e
    fprintf('  ERROR: %s\n', e.message);
end

%% SBE37 - SBE37_parser1.cnv
fprintf('--- SBE37 (cnv) ---\n');
try
    file = fullfile(dataRoot, 'sbe37', 'SBE37_parser1.cnv');
    fprintf('  Parsing: %s\n', file);
    sample_data = SBE37Parse({file}, 'timeSeries');
    save(fullfile(outputDir, 'SBE37_SBE37_parser1_timeSeries.mat'), 'sample_data');
    fprintf('  OK: %d variables, %d time samples\n', ...
        length(sample_data.variables), length(sample_data.dimensions{1}.data));
catch e
    fprintf('  ERROR: %s\n', e.message);
end

%% SBE37 - SBE37_15592_2411.cnv
fprintf('--- SBE37 (cnv 2) ---\n');
try
    file = fullfile(dataRoot, 'sbe37', 'SBE37_15592_2411.cnv');
    fprintf('  Parsing: %s\n', file);
    sample_data = SBE37Parse({file}, 'timeSeries');
    save(fullfile(outputDir, 'SBE37_SBE37_15592_2411_timeSeries.mat'), 'sample_data');
    fprintf('  OK: %d variables, %d time samples\n', ...
        length(sample_data.variables), length(sample_data.dimensions{1}.data));
catch e
    fprintf('  ERROR: %s\n', e.message);
end

%% SBE37SM - sbe37smp-rs232_03722564_2025_11_04C.cnv
fprintf('--- SBE37SM ---\n');
try
    file = fullfile(dataRoot, 'sbe37', 'sbe37smp-rs232_03722564_2025_11_04C.cnv');
    fprintf('  Parsing: %s\n', file);
    sample_data = SBE37SMParse({file}, 'timeSeries');
    save(fullfile(outputDir, 'SBE37SM_sbe37smp_03722564_timeSeries.mat'), 'sample_data');
    fprintf('  OK: %d variables, %d time samples\n', ...
        length(sample_data.variables), length(sample_data.dimensions{1}.data));
catch e
    fprintf('  ERROR: %s\n', e.message);
end

%% SBE39 - SBE39_5840_2411.asc
fprintf('--- SBE39 ---\n');
try
    file = fullfile(dataRoot, 'sbe39', 'SBE39_5840_2411.asc');
    fprintf('  Parsing: %s\n', file);
    sample_data = SBE39Parse({file}, 'timeSeries');
    save(fullfile(outputDir, 'SBE39_SBE39_5840_2411_timeSeries.mat'), 'sample_data');
    fprintf('  OK: %d variables, %d time samples\n', ...
        length(sample_data.variables), length(sample_data.dimensions{1}.data));
catch e
    fprintf('  ERROR: %s\n', e.message);
end

%% SBE56 - SBE56_7517_2411.cnv
fprintf('--- SBE56 ---\n');
try
    file = fullfile(dataRoot, 'sbe56', 'SBE56_7517_2411.cnv');
    fprintf('  Parsing: %s\n', file);
    sample_data = SBE56Parse({file}, 'timeSeries');
    save(fullfile(outputDir, 'SBE56_SBE56_7517_2411_timeSeries.mat'), 'sample_data');
    fprintf('  OK: %d variables, %d time samples\n', ...
        length(sample_data.variables), length(sample_data.dimensions{1}.data));
catch e
    fprintf('  ERROR: %s\n', e.message);
end

%% SBE26 - SBE26_1711_2409_NEW.tid
fprintf('--- SBE26 ---\n');
try
    file = fullfile(dataRoot, 'sbe26', 'SBE26_1711_2409_NEW.tid');
    fprintf('  Parsing: %s\n', file);
    sample_data = SBE26Parse({file}, 'timeSeries');
    save(fullfile(outputDir, 'SBE26_SBE26_1711_2409_NEW_timeSeries.mat'), 'sample_data');
    fprintf('  OK: %d variables, %d time samples\n', ...
        length(sample_data.variables), length(sample_data.dimensions{1}.data));
catch e
    fprintf('  ERROR: %s\n', e.message);
end

fprintf('\n=== Done! Reference files saved to: ===\n');
fprintf('%s\n', outputDir);
dir(fullfile(outputDir, '*.mat'));
