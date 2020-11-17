
x=0
while [ $x -le 5 ]
do
    http POST http://127.0.0.1:8000/new_transaction < tx_data.json
    http POST http://127.0.0.1:8000/new_transaction < tx_data_2.json
    x=$(( $x + 1 ))
done
