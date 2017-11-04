function output = query(cnn, sql_string)
    % query some data
    sqlstring=sprintf(sql_string);
    % fetch the data from the db
    output = select(cnn,sqlstring);
end

