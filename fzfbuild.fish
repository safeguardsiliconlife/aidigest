# Defined interactively
function fzfbuild --description 'Build a single file from interactively selected files'
    # Parse arguments
    set -l output_file "byfzfbuild"
    set -l help_flag 0
    set -l all_flag 0
    set -l exclude_flag 0

    for i in (seq 1 (count $argv))
        switch $argv[$i]
            case -h --help
                set help_flag 1
            case -o --output
                if test (count $argv) -gt $i
                    set output_file $argv[(math $i + 1)]
                end
            case -a --all
                set all_flag 1
            case -e --exclude
                set exclude_flag 1
        end
    end

    # Display help if requested
    if test $help_flag -eq 1
        echo "Usage: fzfbuild [options]"
        echo ""
        echo "Build a single file from interactively selected files or directories"
        echo ""
        echo "Options:"
        echo "  -h, --help              Show this help message"
        echo "  -o, --output FILENAME   Specify output filename (default: 'build')"
        echo "  -a, --all              Include all files and folders in current directory"
        echo "  -e, --exclude          Select files to exclude from the build"
        echo ""
        echo "Controls:"
        echo "  TAB                     Select a file/directory"
        echo "  ENTER                   Confirm selection and create build file"
        echo "  ESC                     Cancel selection"
        return 0
    end

    # Check if required tools are installed
    if not type -q fzf
        echo "Error: fzf is required but not installed" >&2
        return 1
    end
    if not type -q fd
        echo "Error: fd is required but not installed" >&2
        return 1
    end

    # Temporary file to store selected paths
    set -l temp_file (mktemp)
    set -l exclude_file (mktemp)

    if test $all_flag -eq 1
        # If --all flag is used, get all files and directories
        fd --type f --type d | sort > $temp_file
    else if test $exclude_flag -eq 1
        # If --exclude flag is used, first get all files
        fd --type f --type d | sort > $temp_file
        
        # Then let user select files to exclude
        echo "Select files/folders to EXCLUDE with TAB, then press Enter when done"
        cat $temp_file | fzf --multi --preview 'test -d {} && fd --type f . {} || cat {}' --prompt="Select files/folders to EXCLUDE (TAB to select, Enter when done): " | while read -l selected
            echo $selected >> $exclude_file
        end

        # Remove excluded files from temp_file
        if test -s $exclude_file
            set -l new_temp (mktemp)
            comm -23 $temp_file $exclude_file > $new_temp
            mv $new_temp $temp_file
        end
    else
        # Original interactive selection behavior
        echo "Select files/folders with TAB, then press Enter when done"
        fd --type f --type d | fzf --multi --preview 'test -d {} && fd --type f . {} || cat {}' --prompt="Select files/folders (TAB to select, Enter when done): " | while read -l selected
            if test -d $selected
                # For directories, add all files within
                fd --type f . $selected | sort >> $temp_file
            else
                # For files, add directly
                echo $selected >> $temp_file
            end
        end
    end

    # If no selection was made, exit
    if test ! -s $temp_file
        echo "No files selected. Exiting." >&2
        rm $temp_file
        if test -f $exclude_file
            rm $exclude_file
        end
        return 1
    end

    # Create the build file with file contents and separators
    echo "" > $output_file

    cat $temp_file | while read -l file
        echo "#// START $file //#" >> $output_file
        echo "" >> $output_file
        cat $file >> $output_file
        echo "" >> $output_file
        echo "#// END $file //#" >> $output_file
        echo "" >> $output_file
    end

    echo "Created $output_file with "(count < $temp_file)" files"

    # Output the full file paths that were written to the build
    echo "Files included in $output_file:"
    cat $temp_file

    # Clean up
    rm $temp_file
    if test -f $exclude_file
        rm $exclude_file
    end
end
