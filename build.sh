cd frontend/
npm run build
rm -rf ../ether_ghost/public
mv dist ../ether_ghost/public
cd ../ether_ghost
# TODO: build etherGhost packages
