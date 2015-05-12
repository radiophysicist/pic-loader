.PHONY : doc clean debclean deb


all:	deb debclean


deb: debclean
	submodules/write-dch/write_dch -b
	fakeroot debian/rules binary


doc:
	doxygen


debclean:
	debclean


clean:	debclean
	rm -f ./src/*.pyc


distclean: clean
	rm -rf ./doc/*
