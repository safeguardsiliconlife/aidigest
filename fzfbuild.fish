function fzfbuild -d "Build a single file from interactively selected files"
    # Parse arguments
    set -l output_file "byfzfbuild"
    set -l help_flag 0
    
    for i in (seq 1 (count $argv))
        switch $argv[$i]
            case -h --help
                set help_flag 1
            case -o --output
                if test (count $argv) -gt $i
                    set output_file $argv[(math $i + 1)]
                end
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

    # Use fzf to interactively select files or directories
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

    # If no selection was made, exit
    if test ! -s $temp_file
        echo "No files selected. Exiting." >&2
        rm $temp_file
        return 1
    end

    # Create the build file with file contents and separators
    echo "" > $output_file
    
    cat $temp_file | while read -l file
        echo "# $file" >> $output_file
        echo "" >> $output_file
        cat $file >> $output_file
        echo "" >> $output_file
        echo "# End of $file" >> $output_file
        echo "# ----------------------------------------" >> $output_file
        echo "" >> $output_file
    end

    echo "Created $output_file with "(count < $temp_file)" files"
    
    # Output the full file paths that were written to the build
    echo "Files included in $output_file:"
    cat $temp_file
    
    # Clean up
    rm $temp_file
end
