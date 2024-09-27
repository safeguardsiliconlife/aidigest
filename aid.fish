function aid
    set -l base_dir $PWD

    if test (count $argv) -gt 0
        switch $argv[1]
            case "-l"
                if test (count $argv) -gt 1
                    set base_dir $argv[2]
                end

                set -l aidigest_dir $base_dir/aidigest
                if not test -d $aidigest_dir
                    echo "No aidigest folder found in $base_dir"
                    return 1
                end

                set -l recent_folders (command ls -1dt $aidigest_dir/*/ | head -n5)
                if test -z "$recent_folders"
                    echo "No aidigest outputs found in $aidigest_dir"
                    return 1
                end

                echo "Recent aidigest outputs:"
                for folder in $recent_folders
                    set -l info_file $folder/info.txt
                    if test -f $info_file
                        set -l timestamp (basename $folder)
                        echo "Timestamp: $timestamp"
                        cat $info_file
                        echo "----------------------------------------"
                    end
                end

                # Set LATEST_AIDIGEST to the most recent aidigest file
                set -l latest_folder $recent_folders[1]
                set -l aidigest_file $latest_folder/aidigest
                if test -f $aidigest_file
                    set -g LATEST_AIDIGEST (realpath $aidigest_file)
                    echo "LATEST_AIDIGEST set to: $LATEST_AIDIGEST"
                else
                    echo "No aidigest file found in the most recent folder"
                end

            case "-v"
                if set -q LATEST_AIDIGEST
                    if test -f $LATEST_AIDIGEST
                        vim $LATEST_AIDIGEST
                    else
                        echo "The file $LATEST_AIDIGEST does not exist."
                        return 1
                    end
                else
                    echo "LATEST_AIDIGEST is not set. Run aid or aid -l first."
                    return 1
                end

            case '*'
                # Show the command and ask for confirmation
                set -l command_to_run "aidigest $argv"
                echo "About to run the following command:"
                echo $command_to_run
                read -l -P "Do you want to proceed? [y/N] " confirm

                switch $confirm
                    case Y y
                        # Run aidigest with all provided arguments
                        eval $command_to_run

                        # After running, set LATEST_AIDIGEST to the newly created aidigest file
                        set -l latest_folder (command ls -1dt $PWD/aidigest/*/ | head -n1)
                        if test -n "$latest_folder"
                            set -l aidigest_file $latest_folder/aidigest
                            if test -f $aidigest_file
                                set -g LATEST_AIDIGEST (realpath $aidigest_file)
                                echo "LATEST_AIDIGEST set to: $LATEST_AIDIGEST"
                            end
                        end
                    case '' N n
                        echo "Command cancelled."
                        return 1
                end
        end
    else
        echo "Usage:"
        echo "  aid [aidigest arguments]  - Run aidigest with given arguments"
        echo "  aid -l [directory]        - List top 5 recent aidigest outputs"
        echo "  aid -v                    - Open the latest aidigest file in Vim"
    end
end
